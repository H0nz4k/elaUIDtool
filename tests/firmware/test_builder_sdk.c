/* Real ELATEC SDK declarations, simulated RF/USB; no physical-reader claims. */
#include "twn4.sys.h"
#include "apptools.h"
#include "builder_config.h"
#include <assert.h>
#include <setjmp.h>
#include <string.h>
int bld_uid_main(void);
int printf(const char *format, ...);
static jmp_buf done;
static const char *scenario;
static unsigned long ticks;
static int polls, frames, beeps, lights, host_set, sound_on;
static char outputs[20][64];
static int is(const char *name) { return strcmp(scenario, name) == 0; }
void LEDInit(int leds) { assert(leds == (REDLED | GREENLED)); lights = 0; }
void LEDOn(int leds) { lights |= leds; }
void LEDOff(int leds) { lights &= ~leds; }
void BeepOn(int volume, int frequency)
{
    assert(!sound_on);
    if (is("wrong") || is("reject")) {
        assert(volume == 77 && frequency == 1500);
        assert((lights & REDLED) && !(lights & GREENLED));
    } else {
        assert(volume == 42 && frequency == 3500);
        /* Three beeps, only two flashes, synchronized at the start of each pulse. */
        assert((beeps % 3 < 2) ? !!(lights & GREENLED) : !(lights & GREENLED));
        assert(!(lights & REDLED));
    }
    beeps++;
    sound_on = 1;
}
void BeepOff(void) { sound_on = 0; }
void Delay(unsigned long duration)
{
    ticks += duration;
    if (is("host-down") && ticks >= 1000) longjmp(done, 1);
}
unsigned long GetSysTicks(void) { return ticks; }
bool SetHostChannel(int channel) { assert(channel == CHANNEL_USB); host_set++; return true; }
int GetUSBDeviceState(void) { return is("host-down") ? USB_DEVICE_STATE_DEFAULT : USB_DEVICE_STATE_CONFIGURED; }
void USBRemoteWakeup(void) { assert(0); }
void GetSupportedTagTypes(unsigned int *lf, unsigned int *hf)
{
    *lf = TAGMASK(LFTAG_EM4102);
    *hf = TAGMASK(HFTAG_MIFARE) | TAGMASK(HFTAG_BLE) | TAGMASK(HFTAG_NFCP2P);
}
void SetTagTypes(unsigned int lf, unsigned int hf)
{
    assert(lf == TAGMASK(LFTAG_EM4102));
    assert(hf == TAGMASK(HFTAG_MIFARE));
}
bool SearchTag(int *type, int *bits, byte *id, int capacity)
{
    const byte raw[] = {0x81, 0x3F, 0x9A, 0x04};
    assert(capacity == 32 && !sound_on);
    polls++;
    ticks += 100;
    if (polls >= 15) longjmp(done, 1);
    *type = HFTAG_MIFARE;
    *bits = is("wrong") ? 320 : 32;
    memcpy(id, raw, sizeof(raw));
    if (is("wrong")) return true;
    return polls <= 4 || (polls >= 9 && polls <= 11);
}
void HostWriteString(const char *text)
{
    if (strcmp(text, "\r") == 0) return;
    assert(frames < 20 && strlen(text) < sizeof(outputs[0]));
    strcpy(outputs[frames++], text);
}
int main(int argc, char **argv)
{
    int i, expected;
    assert(argc == 2);
    scenario = argv[1];
    if (!setjmp(done)) bld_uid_main();
    assert(host_set == 1 && !sound_on);
    expected = is("wrong") || is("reject") || is("host-down") ? 0 : (BLD_REPEAT_MS ? 7 : 2);
    assert(frames == expected);
    for (i = 0; i < frames; i++) assert(strcmp(outputs[i], "049A3F81") == 0);
    if (is("host-down")) assert(polls == 0 && beeps == 0);
    else if (is("wrong")) assert(beeps == 1);
    else if (is("reject")) assert(beeps == 2);
    else assert(beeps == expected * 3);
    printf("PASS: UID builder %s, %d frames, %d beeps, independent volume/tone/LED counts\n", scenario, frames, beeps);
    return 0;
}
