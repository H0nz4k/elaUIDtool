"""Společné sestavení User App s nezměněným OS z lokálního DevPacku 5.20."""
from __future__ import annotations

from dataclasses import dataclass
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

from .bix_container import extract_system_images, parse, system_pairs, validate_multi

BASE_NAME = "TWN4_xCx520_STD207_Multi_CDC_Standard.bix"
KEYBOARD_BASE_NAME = "TWN4_xKx520_STD207_Multi_Keyboard_Standard.bix"
FAMILY_NAMES = ("TWN4_CCx520.bix", "TWN4_MCx520.bix", "TWN4_NCx520.bix")


@dataclass(frozen=True)
class ToolchainOptions:
    gcc: str | None = None
    objcopy: str | None = None
    makeapp_runtime: str | None = None


def resolve_std_template(pack: Path) -> Path:
    for relative in ("Apps/App_STD207_Standard_temp.c", "Apps/Samples/Standard/App_STD207_Standard.c"):
        candidate = pack / relative
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Chybí Apps/App_STD207_Standard_temp.c nebo Apps/Samples/Standard/App_STD207_Standard.c")


def resolve_inputs(pack: Path, base_bix: Path | None = None, *, usb_type: str = "cdc") -> list[Path]:
    if usb_type not in ("cdc", "keyboard"):
        raise ValueError("Systémový USB typ musí být CDC nebo keyboard.")
    if base_bix is not None:
        if not base_bix.is_file():
            raise FileNotFoundError(f"Base BIX neexistuje: {base_bix}")
        return [base_bix.resolve()]
    names = FAMILY_NAMES if usb_type == "cdc" else tuple(name.replace("Cx520", "Kx520") for name in FAMILY_NAMES)
    families = [next((d / name for d in (pack / "Apps", pack / "Firmware")
                      if (d / name).is_file()), None) for name in names]
    if all(families):
        return [path for path in families if path is not None]
    base_name = BASE_NAME if usb_type == "cdc" else KEYBOARD_BASE_NAME
    base = pack / "Firmware" / base_name
    if not base.is_file():
        raise FileNotFoundError(f"Chybí Firmware/{base_name} nebo všechny tři rodiny {', '.join(names)}")
    return [base]


def validate_devpack(pack: Path, *, standard: bool = True, usb_type: str = "cdc") -> list[str]:
    required = ["Tools/makeapp.exe", "Tools/Yagarto-20110328/bin/arm-none-eabi-gcc.exe",
                "Tools/Yagarto-20110328/bin/arm-none-eabi-objcopy.exe"]
    required += [f"Tools/sys/{name}" for name in
                 ("twn4.sys.h", "apptools.h", "twn4.crt.c", "app.ld", "libapp.a")]
    missing = [name for name in required if not (pack / name).is_file()]
    if standard:
        try:
            resolve_std_template(pack)
        except FileNotFoundError:
            missing.append("Apps/App_STD207_Standard_temp.c nebo Apps/Samples/Standard/App_STD207_Standard.c")
    try:
        resolve_inputs(pack, usb_type=usb_type)
    except FileNotFoundError:
        names = FAMILY_NAMES if usb_type == "cdc" else tuple(name.replace("Cx520", "Kx520") for name in FAMILY_NAMES)
        missing.extend(f"Apps/{name}" for name in names if not (pack / "Apps" / name).is_file())
        missing.append(f"nebo Firmware/{BASE_NAME if usb_type == 'cdc' else KEYBOARD_BASE_NAME}")
    return missing


def _executable(value: str) -> str:
    if Path(value).is_file():
        return str(Path(value).resolve())
    found = shutil.which(value)
    if found:
        return found
    raise FileNotFoundError(f"Chybí nástroj: {value}")


@dataclass(frozen=True)
class AppBuildResult:
    bix_path: Path
    hex_path: Path
    manifest_path: Path


def build_user_app(
    *, pack: Path, output_dir: Path, name: str, app_chars: str, app_version: int,
    files: dict[str, str], sources: list[str], external_sources: tuple[Path, ...] = (),
    defines: tuple[str, ...] = (), options: ToolchainOptions | None = None,
    base_bix: Path | None = None, branch: str = "0520", metadata: dict | None = None,
    usb_type: str = "cdc",
) -> AppBuildResult:
    options = options or ToolchainOptions()
    branch = branch.strip().lower().removeprefix("0x").zfill(4)
    if branch != "0520":
        raise ValueError("Export je ověřen pro DevPack 5.20 (branch 0520). Použij tento DevPack.")
    pack, output_dir = pack.resolve(), output_dir.resolve()
    sys_dir = pack / "Tools" / "sys"
    for item in ("twn4.sys.h", "apptools.h", "twn4.crt.c", "app.ld", "libapp.a"):
        if not (sys_dir / item).is_file():
            raise FileNotFoundError(f"Chybí součást SDK: {sys_dir / item}")
    yagarto = pack / "Tools" / "Yagarto-20110328"
    gcc = _executable(options.gcc or str(yagarto / "bin" / "arm-none-eabi-gcc.exe"))
    objcopy = _executable(options.objcopy or str(yagarto / "bin" / "arm-none-eabi-objcopy.exe"))
    makeapp = pack / "Tools" / "makeapp.exe"
    if not makeapp.is_file():
        raise FileNotFoundError(f"Chybí {makeapp}")
    make_command = [str(makeapp)]
    if options.makeapp_runtime:
        make_command.insert(0, _executable(options.makeapp_runtime))
    elif os.name != "nt":
        raise ValueError("Na Linuxu zadej --gcc, --objcopy a --makeapp-runtime mono.")
    inputs = resolve_inputs(pack, base_bix, usb_type=usb_type)
    env = os.environ.copy()
    if os.name != "nt":
        env.setdefault("COMPUTERNAME", platform.node() or "elaUIDtool")
        env.setdefault("USERDOMAIN", "LOCAL")
        env.setdefault("USERNAME", getpass.getuser())
    output_dir.mkdir(parents=True, exist_ok=True)
    # A failed build cannot return an older BIX. Publish only validated outputs.
    with tempfile.TemporaryDirectory(prefix="twn4-", dir=output_dir) as temporary:
        work = Path(temporary)
        for filename, content in files.items():
            (work / filename).write_text(content, encoding="utf-8", newline="\n")
        elf, hex_path, bix = (work / f"{name}{ext}" for ext in (".elf", ".hex", ".bix"))
        map_path = work / f"{name}.map"
        log = []

        def run(command: list[str]) -> None:
            log.append(json.dumps(command, ensure_ascii=False))
            result = subprocess.run(command, cwd=work, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.append(result.stdout)
            if result.returncode:
                failure = output_dir / "last_build_failed.log"
                failure.write_text("\n".join(log), encoding="utf-8")
                raise RuntimeError(f"Sestavení selhalo (kód {result.returncode}). {failure}\n{result.stdout[-4000:]}")

        command = [gcc, "-std=c99", "-mcpu=cortex-m0", "-mthumb", "-Os",
                   "-ffunction-sections", "-fdata-sections", "-fomit-frame-pointer",
                   "-Wall", "-Wextra", "-Wstrict-prototypes",
                   f"-DAPPCHARS={app_chars}", f"-DAPPVERSION=0x{app_version:04X}",
                   f"-DVERSION=0x{app_version:04X}", f"-I{work}", f"-I{sys_dir}"]
        command += [f"-D{define}" for define in defines]
        if os.name != "nt":
            command += ["-isystem", str(yagarto / "arm-none-eabi" / "include"),
                        f"-L{yagarto / 'arm-none-eabi' / 'lib' / 'thumb' / 'v6m'}"]
        command += [str(sys_dir / "twn4.crt.c")]
        command += [str(work / source) for source in sources]
        command += [str(source) for source in external_sources]
        command += ["-nostartfiles", f"-T{sys_dir / 'app.ld'}",
                    f"-Wl,--gc-sections,-e,AppHeader,-Map={map_path},--cref,--no-warn-mismatch",
                    str(sys_dir / "libapp.a"), "-lc", "-o", str(elf)]
        run(command)
        run([objcopy, "-O", "ihex", str(elf), str(hex_path)])
        if len(inputs) == 1:
            staged = extract_system_images(inputs[0], work)
        else:
            staged = []
            for path in inputs:
                dest = work / path.name
                shutil.copy2(path, dest)
                staged.append(dest)
        original = [pair for path in staged for pair in system_pairs(parse(path.read_bytes()))]
        if len(original) != 3:
            raise ValueError("Základ musí obsahovat právě tři systémové rodiny TWN4 5.20.")
        run(make_command + ["-v4", "-tTWN4", "-nTWN4", "-b0520"] +
            [f"-i{path}" for path in staged] + [f"-h{hex_path}", f"-o{bix}"])
        packed = bix.read_bytes()
        validate_multi(packed)
        resulting = system_pairs(parse(packed))
        if [(a.encoded, b.encoded) for a, b in original] != [(a.encoded, b.encoded) for a, b in resulting]:
            raise ValueError("Výstup změnil původní systémové obrazy; export byl odmítnut.")
        manifest = {**(metadata or {}), "devpack": "5.20", "usb_type": usb_type, "app": app_chars,
                    "app_version": f"0x{app_version:04X}", "firmware": bix.name,
                    "bytes": len(packed), "sha256": hashlib.sha256(packed).hexdigest(),
                    "base_images": [path.name for path in inputs],
                    "hardware_tested": False}
        manifest_name = f"{name}.json"
        (work / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (work / f"{name}.log").write_text("\n".join(log), encoding="utf-8")
        for filename in [*files, elf.name, hex_path.name, map_path.name, bix.name, manifest_name, f"{name}.log"]:
            shutil.copy2(work / filename, output_dir / filename)
    return AppBuildResult(output_dir / bix.name, output_dir / hex_path.name, output_dir / manifest_name)
