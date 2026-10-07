"""Generate and build a UID/registration app from a complete BuilderProject."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.resources import files as resource_files
import json
from pathlib import Path
import re
import zipfile

from .builder import BuilderProject, DataRule, ENCODINGS, FORMATS, Feedback, PHYSICAL_HF
from .fw_export import DEFAULT_DEVPACK, EXPORT_DIR
from .registration import RegistrationConfig, registration_sources
from .twn4_build import ToolchainOptions, build_user_app


def c_string(text: str) -> str:
    # Fixed-width octal escapes prevent escaping/injection and \x swallowing following hex digits.
    return '"' + "".join(c if 32 <= ord(c) <= 126 and c not in ('"', '\\') else f"\\{ord(c):03o}"
                         for c in text) + '"'


def _rule(rule: DataRule) -> str:
    fields = [int(rule.reverse_bits), int(rule.reverse_bytes), rule.first_bit, rule.bit_count,
              ENCODINGS.index(rule.encoding), FORMATS[rule.output_format],
              ("auto", "minimum", "exact").index(rule.length_mode), rule.length,
              int(rule.lowercase), int(rule.strip_zeros), int(rule.append_00)]
    strings = [rule.and_mask, rule.xor_mask, rule.byte_separator, rule.prefix, rule.suffix]
    return "{" + ", ".join([str(value) for value in fields] + [c_string(value) for value in strings]) + "}"


def _mask(tags, default: tuple[int, ...] | None = None) -> str:
    if tags is None and default is None:
        return "0xFFFFFFFFu"
    chosen = default if tags is None else tags
    return f"0x{sum(1 << (tag & 0x1F) for tag in chosen):08X}u"


def config_header(project: BuilderProject) -> str:
    terminator = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "TAB": "\t", "NONE": ""}[project.terminator]
    values = {
        "BLD_HF_MASK": _mask(project.hf_tags, PHYSICAL_HF), "BLD_LF_MASK": _mask(project.lf_tags),
        "BLD_REMOVAL_MS": f"{project.removal_ms}UL", "BLD_REPEAT_MS": f"{project.repeat_ms}UL",
        "BLD_REMOTE_WAKEUP": int(project.remote_wakeup), "BLD_TERMINATOR": c_string(terminator),
    }
    return ('#ifndef BLD_CONFIG_H\n#define BLD_CONFIG_H\n#include "data_rule.h"\n' +
            "\n".join(f"#define {key} {value}" for key, value in values.items()) +
            f"\nstatic const BldRule BLD_HF = {_rule(project.hf)};\nstatic const BldRule BLD_LF = {_rule(project.lf)};\n#endif\n")


def _feedback(pattern: Feedback) -> str:
    colors = {"off": "0", "red": "REDLED", "green": "GREENLED", "both": "(REDLED | GREENLED)"}
    return "{" + ", ".join(str(value) for value in (pattern.volume, pattern.frequency, pattern.beeps,
                                                    pattern.flashes, colors[pattern.led], pattern.on_ms, pattern.off_ms)) + "}"


def feedback_sources(project: BuilderProject) -> dict[str, str]:
    colors = {"off": "0", "red": "REDLED", "green": "GREENLED", "both": "(REDLED | GREENLED)"}
    patterns = "\n".join(f"const BldFeedback BLD_{name.upper()} = {_feedback(getattr(project, name))};"
                         for name in ("startup", "success", "dual_success", "error"))
    if project.channel == "uart":
        host_setup = f"""TCOMParameters parameters;
    parameters.BaudRate = {project.uart_baud};
    parameters.WordLength = COM_WORDLENGTH_8;
    parameters.Parity = COM_PARITY_{project.uart_parity.upper()};
    parameters.StopBits = COM_STOPBITS_{project.uart_stop_bits};
    parameters.FlowControl = COM_FLOWCONTROL_NONE;
    return SetCOMParameters(CHANNEL_COM1, &parameters) && SetHostChannel(CHANNEL_COM1);"""
    else:
        host_setup = "return SetHostChannel(CHANNEL_USB);"
    pid = "USB_PID_KEYBOARD" if project.channel == "keyboard" else "USB_PID_CDC"
    serial = {"off": "OFF", "deviceuid": "DEVICEUID", "production": "PRODUCTION"}[project.usb_serial]
    header = """#ifndef BLD_FEEDBACK_H
#define BLD_FEEDBACK_H
typedef struct { int volume, frequency, beeps, flashes, led, on_ms, off_ms; } BldFeedback;
extern const BldFeedback BLD_STARTUP, BLD_SUCCESS, BLD_DUAL_SUCCESS, BLD_ERROR;
void bld_feedback(const BldFeedback *pattern);
void bld_startup(void);
void bld_idle(void);
int bld_setup_host(void);
int bld_host_ready(void);
#endif
"""
    source = f"""#include "twn4.sys.h"
#include "apptools.h"
#include "feedback.h"
const byte AppManifest[] = {{
    USB_PID, 2, USB_WORD({pid}),
    USB_KEYBOARDREPEATRATE, 1, {project.keyboard_repeat_ms},
    USB_KEYBOARDLAYOUT, 1, USB_KEYBOARDLAYOUT_{project.keyboard_layout.upper()},
    USB_KEYBOARDSENDALTCODES, 1, {int(project.keyboard_alt_codes)},
    USB_SERIALNUMBER, 1, USB_SERIALNUMBER_{serial},
    USB_SUPPORTREMOTEWAKEUP, 1, {int(project.remote_wakeup)},
    EXECUTE_APP, 1, EXECUTE_APP_AUTO,
    ENABLE_WATCHDOG, 1, WATCHDOG_ON,
    TLV_END
}};
{patterns}
void bld_idle(void)
{{
    LEDOff(REDLED | GREENLED);
    LEDOn({colors[project.idle_led]});
}}
void bld_feedback(const BldFeedback *pattern)
{{
    int i, count = pattern->beeps > pattern->flashes ? pattern->beeps : pattern->flashes;
    LEDOff(REDLED | GREENLED);
    for (i = 0; i < count; i++) {{
        if (i < pattern->flashes) LEDOn(pattern->led);
        if (i < pattern->beeps && pattern->volume) BeepOn(pattern->volume, pattern->frequency);
        Delay(pattern->on_ms);
        BeepOff();
        LEDOff(REDLED | GREENLED);
        Delay(pattern->off_ms);
    }}
    bld_idle();
}}
void bld_startup(void)
{{
    LEDInit(REDLED | GREENLED);
    BeepOff();
    bld_feedback(&BLD_STARTUP);
}}
int bld_setup_host(void)
{{
    {host_setup}
}}
int bld_host_ready(void)
{{
    {'return 1;' if project.channel == 'uart' else f'''int state = GetUSBDeviceState();
    if (state == USB_DEVICE_STATE_SUSPENDED && {int(project.remote_wakeup)}) USBRemoteWakeup();
    return state == USB_DEVICE_STATE_CONFIGURED;'''}
}}
"""
    return {"feedback.h": header, "feedback.c": source}


def builder_sources(project: BuilderProject) -> dict[str, str]:
    folder = resource_files("elatec_uid_tool").joinpath("fw_templates", "builder")
    sources = {item.name: item.read_text(encoding="utf-8") for item in folder.iterdir()
               if item.name.endswith((".c", ".h"))}
    sources["builder_config.h"] = config_header(project)
    sources.update(feedback_sources(project))
    if project.mode == "registration":
        sources.pop("App_BLD_UID.c")
        dual = registration_sources(RegistrationConfig())
        dual.pop("registration_signal.c")
        source = dual["App_D2R_DualRegistration.c"]
        source = source.replace('#include "registration_trace.h"', '#include "registration_trace.h"\n#include "builder_config.h"\n#include "feedback.h"')
        source = source.replace("uid.tag_type = (uint8_t)type;", """uid.tag_type = (uint8_t)type;
            if (uid.valid) {
                char converted[BLD_MAX_OUTPUT];
                const BldRule *rule = hf ? &BLD_HF : &BLD_LF;
                int nonzero = 0, i;
                if (!bld_convert(raw, bits, rule, converted, sizeof(converted)) || strlen(converted) > 16)
                    uid.valid = 0;
                else {
                    for (i = 0; converted[i]; i++) nonzero |= converted[i] != '0';
                    if (!nonzero) uid.valid = 0;
                    else strcpy(uid.code, converted);
                }
            }""")
        source = source.replace("GetSupportedTagTypes(&supported_lf, &supported_hf);",
                                "GetSupportedTagTypes(&supported_lf, &supported_hf);\n    supported_lf &= BLD_LF_MASK;\n    supported_hf &= BLD_HF_MASK;")
        source = source.replace("HostWriteString(\"\\r\");", "HostWriteString(BLD_TERMINATOR);")
        # Same proven state machine; only conversion, masks and feedback are configurable.
        dual["App_D2R_DualRegistration.c"] = source
        header = dual["dual_config.h"]
        for name, value in (("D2_REMOVAL_MS", f"{project.removal_ms}u"),
                            ("D2_OTHER_SEARCH_MS", f"{project.other_search_ms}u"),
                            ("D2_HANDOFF_MS", f"{project.handoff_ms}u"),
                            ("D2_RF_PAUSE_MS", f"{project.rf_pause_ms}u"),
                            ("D2_HF_RADIX", 16 if project.hf.output_format == "HEX" else 10),
                            ("D2_LF_RADIX", 16 if project.lf.output_format == "HEX" else 10),
                            ("D2_APP_ID", '"BLD0.60"')):
            header = re.sub(rf"^#define {name} .+$", f"#define {name} {value}", header, flags=re.MULTILINE)
        dual["dual_config.h"] = header
        sources.update(dual)
        sources["registration_signal.c"] = """#include "twn4.sys.h"
#include "apptools.h"
#include "registration_signal.h"
#include "feedback.h"
void d2_signal_init(void) { bld_startup(); }
void d2_signal_action(const D2Reader *reader, D2Action action)
{
    switch (action) {
    case D2_HF_FOUND: case D2_LF_FOUND:
        if (reader->hf.valid && reader->lf.valid) bld_feedback(&BLD_DUAL_SUCCESS);
        break;
    case D2_SINGLE_READY: bld_feedback(&BLD_SUCCESS); break;
    case D2_INVALID_PAIR: case D2_TIMEOUT: bld_feedback(&BLD_ERROR); break;
    case D2_READY: case D2_END_SINGLE: case D2_SEND_SECOND: bld_idle(); break;
    default: break;
    }
}
"""
    return sources


@dataclass(frozen=True)
class BuilderResult:
    bix_path: Path
    manifest_path: Path
    project_path: Path
    source_zip: Path


def build_project(project: BuilderProject, *, devpack: Path | None = None, output_dir: Path | None = None,
                  toolchain: ToolchainOptions | None = None) -> BuilderResult:
    # Revalidate even if a caller supplied an object built by bypassing the dataclass constructor.
    project = BuilderProject.from_dict(project.to_dict())
    digest = hashlib.sha256(project.to_json().encode("utf-8")).hexdigest()[:10]
    usb_type = "keyboard" if project.channel == "keyboard" else "cdc"
    name = f"TWN4_x{'K' if usb_type == 'keyboard' else 'C'}x520_BLD060_{project.channel.upper()}_{project.reader_model}_{digest}"
    out = output_dir or EXPORT_DIR / "builder" / digest
    files = builder_sources(project)
    sources = ["data_rule.c", "feedback.c"]
    if project.mode == "uid":
        sources += ["App_BLD_UID.c"]
    else:
        sources += ["App_D2R_DualRegistration.c", "dual_core.c", "registration_signal.c", "registration_trace.c"]
    result = build_user_app(pack=devpack or DEFAULT_DEVPACK, output_dir=out, name=name,
                            app_chars="BLD", app_version=0x0060, files=files, sources=sources, options=toolchain, usb_type=usb_type,
                            metadata={"mode": project.mode, "channel": project.channel, "project": project.to_dict(),
                                      "source_data": "UID", "output_order": ["HF", "LF"] if project.mode == "registration" else [],
                                      "exact_length_overflow": "reject, never truncate"})
    project_path = result.bix_path.with_suffix(".project.json")
    project_path.write_text(project.to_json(), encoding="utf-8")
    source_zip = result.bix_path.with_suffix(".sources.zip")
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, text in files.items():
            archive.writestr(filename, text)
        archive.writestr("project.json", project.to_json())
        archive.writestr("manifest.json", result.manifest_path.read_text(encoding="utf-8"))
        archive.writestr("README.txt", "Generated by elaUIDtool. Requires a local licensed TWN4 DevPack 5.20.\n"
                         "Rebuild: elatec-uid build-project --project project.json --devpack PATH\n"
                         "SDK/OS files are not included. The firmware has not been hardware-tested by the builder.\n")
    return BuilderResult(result.bix_path, result.manifest_path, project_path, source_zip)
