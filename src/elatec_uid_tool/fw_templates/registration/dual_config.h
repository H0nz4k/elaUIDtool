#ifndef DUAL_CONFIG_H
#define DUAL_CONFIG_H

/* Dedicated LF + HF enrollment app, USB CDC (virtual COM).
 * Do not copy the truncated Wiegand 3+5 conversion from App_W35. */
#ifndef D2_HOST_CHANNEL
#define D2_HOST_CHANNEL CHANNEL_USB
#endif
#define D2_UART_BAUD 19200
#define D2_REMOVAL_MS 300u
#define D2_RF_PAUSE_MS 100u
#define D2_OTHER_SEARCH_MS 2000u
#define D2_PAIR_TIMEOUT_MS 30000u
#define D2_HANDOFF_MS 200u
#define D2_FOUND_PULSES 2u
#define D2_SINGLE_PULSES 1u
#define D2_FOUND_PULSE_MS 60u
#define D2_FOUND_VOLUME 100
/* Jidelna preserves the Windows DCB but does not explicitly assert DTR.
 * Test sessions use DTR; normal mode retains USB-configured compatibility. */
#define D2_REQUIRE_DTR 0

/* Defaults: full UID HEX, original length. DEC uses the same unsigned value.
 * This file is generated per export by elaUIDtool. */
#define D2_APP_ID "D2R0.15"
#define D2_LF_RADIX 16
#define D2_HF_RADIX 16
#define D2_LF_REVERSE_BYTES 0
#define D2_LF_APPEND_00 0
#define D2_HF_REVERSE_BYTES 0
#define D2_HF_APPEND_00 0

#endif
