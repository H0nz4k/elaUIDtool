#include "twn4.sys.h"
#include "apptools.h"
#include "dual_config.h"
#include "registration_signal.h"

void d2_signal_init(void)
{
    LEDInit(REDLED | GREENLED);
    BeepOff();
    LEDOff(REDLED);
    LEDOn(GREENLED);
    SetVolume(D2_FOUND_VOLUME);
}

static void found(unsigned int count)
{
    unsigned int i;
    LEDOff(REDLED | GREENLED);
    /* Each pulse is 60ms on/off; RF calls never stretch feedback. */
    for (i = 0; i < count; i++) {
        LEDOn(GREENLED);
        BeepOn(D2_FOUND_VOLUME, 4000);
        Delay(D2_FOUND_PULSE_MS);
        BeepOff();
        LEDOff(GREENLED);
        Delay(D2_FOUND_PULSE_MS);
    }
    LEDOn(GREENLED);
}

void d2_signal_action(const D2Reader *reader, D2Action action)
{
    switch (action) {
    case D2_HF_FOUND:
    case D2_LF_FOUND:
        if (reader->hf.valid && reader->lf.valid) found(D2_FOUND_PULSES);
        break;
    case D2_READY:
    case D2_END_SINGLE:
    case D2_SEND_SECOND:
        LEDOff(REDLED);
        LEDOn(GREENLED);
        break;
    case D2_INVALID_PAIR:
    case D2_TIMEOUT:
        BeepOff();
        LEDOff(GREENLED);
        LEDOn(REDLED);
        BeepLow();
        break;
    case D2_SINGLE_READY:
        found(D2_SINGLE_PULSES);
        break;
    case D2_SEND_FIRST:
    case D2_NONE:
        break;
    }
}
