/* Opt-in diagnostics in the real registration app. Normal output is UID+CR.
 * Explicit !T CR enables the standalone test; !N resets only while paused.
 * Port transitions never reset a pending HF/LF pair. */
#include "twn4.sys.h"
#include "apptools.h"
#include "dual_config.h"
#include "registration_trace.h"
#include "registration_signal.h"

static int trace_on, test_mode, armed, parser;
static byte pending_command;
static unsigned int supported_lf, supported_hf, htries, hhits, ltries, lhits;
static int last_type, last_bits, last_rf;
static unsigned int last_error;
static unsigned int last_search_ms;
static char band;
static uint32_t heartbeat_at, read_at;
static char line[360];

static const char *stage_name(D2Stage stage)
{
    switch (stage) {
    case D2_SCAN: return "SCAN";
    case D2_WAIT_HF: return "WAIT_HF";
    case D2_WAIT_LF: return "WAIT_LF";
    case D2_WAIT_SEND_FIRST: return "WAIT_SEND_FIRST";
    case D2_WAIT_SEND_SECOND: return "WAIT_SEND_SECOND";
    case D2_WAIT_REMOVE_FINAL: return "WAIT_REMOVE_FINAL";
    case D2_LOCKED: return "LOCKED";
    }
    return "UNKNOWN";
}

static const char *action_name(D2Action action)
{
    switch (action) {
    case D2_SEND_FIRST: return "SEND_FIRST";
    case D2_END_SINGLE: return "END_SINGLE";
    case D2_SEND_SECOND: return "SEND_SECOND";
    case D2_SINGLE_READY: return "SINGLE_READY";
    case D2_HF_FOUND: return "HF_FOUND";
    case D2_LF_FOUND: return "LF_FOUND";
    case D2_READY: return "READY";
    case D2_TIMEOUT: return "TIMEOUT";
    case D2_INVALID_PAIR: return "INVALID_PAIR";
    case D2_NONE: return "NONE";
    }
    return "UNKNOWN";
}

static int dtr(void)
{
#if D2_HOST_CHANNEL == CHANNEL_USB
    return (GetCDCControlLineState() & CDC_CONTROL_LINE_STATE_DTR) != 0;
#else
    return 1;
#endif
}

int d2_host_ready(void)
{
#if D2_HOST_CHANNEL == CHANNEL_USB
    if (GetUSBDeviceState() != USB_DEVICE_STATE_CONFIGURED) return 0;
    if ((test_mode || D2_REQUIRE_DTR) && !dtr()) return 0;
#endif
    return !test_mode || armed;
}

static void status(D2Reader *reader)
{
    sprintf(line, "STATUS " D2_APP_ID " stage=%s band=%c test=%d armed=%d usb=%d dtr=%d haveHF=%d haveLF=%d Htries=%u Hhits=%u Ltries=%u Lhits=%u type=0x%02X bits=%d rf=%d searchMs=%u error=0x%08X\r",
            stage_name(reader->stage), band, test_mode, armed,
            GetUSBDeviceState(), dtr(), reader->hf.valid, reader->lf.valid,
            htries, hhits, ltries, lhits, last_type, last_bits, last_rf, last_search_ms, last_error);
    HostWriteString(line);
    sprintf(line, "CONFIG HF=%s LF=%s\r",
            D2_HF_RADIX == 16 ? "HEX" : "DEC", D2_LF_RADIX == 16 ? "HEX" : "DEC");
    HostWriteString(line);
}

static void identity(void)
{
    char version[96];
    memset(version, 0, sizeof(version));
    GetVersionString(version, sizeof(version) - 1);
    HostWriteString("VERSION ");
    HostWriteString(version);
    HostWriteString("\r");
    sprintf(line, "MASKS LF=0x%08X HF=0x%08X\r", supported_lf, supported_hf);
    HostWriteString(line);
}

void d2_trace_init(unsigned int lf, unsigned int hf)
{
    supported_lf = lf;
    supported_hf = hf;
    trace_on = test_mode = armed = parser = 0;
    htries = hhits = ltries = lhits = 0;
    last_type = last_bits = last_rf = 0;
    last_error = 0;
    last_search_ms = 0;
    heartbeat_at = read_at = (uint32_t)GetSysTicks();
    band = 'P';
}

static void command(D2Reader *reader, byte value)
{
    int denied = 0;
    if (value == 'T') { trace_on = test_mode = 1; armed = 0; }
    else if (value == 'N' && test_mode && !armed && supported_lf && supported_hf) {
        D2Timing timing = reader->timing;
        d2_init(reader, timing);
        d2_signal_init();
        htries = hhits = ltries = lhits = 0;
    } else if (value == 'G' && test_mode && reader->stage == D2_SCAN) armed = 1;
    else if (value == 'P' && test_mode) armed = 0;
    else if (value == 'Q') {
        HostWriteString("ACK Q " D2_APP_ID "\r");
        trace_on = test_mode = armed = 0;
        return;
    } else if (value != 'S') denied = 1;
    if (!denied && value == 'S') trace_on = 1;
    sprintf(line, "%s %c " D2_APP_ID "\r", denied ? "DENIED" : "ACK", value);
    HostWriteString(line);
    status(reader);
    if (value == 'T' || value == 'S') identity();
}

void d2_trace_poll(D2Reader *reader)
{
    /* A frame is exactly ! + uppercase command + CR. Stray bytes are ignored. */
    while (HostTestByte()) {
        byte value = HostReadByte();
        if (value == '!') { parser = 1; continue; }
        if (parser == 1 && value >= 'A' && value <= 'Z') {
            pending_command = value;
            parser = 2;
        } else {
            if (parser == 2 && value == '\r') command(reader, pending_command);
            parser = 0;
        }
    }
}

void d2_trace_band(char selection) { band = selection; }

void d2_trace_read(char selection, int type, int bits, int found, int rf,
                   unsigned int error, unsigned int search_ms, const D2Uid *uid)
{
    uint32_t now = (uint32_t)GetSysTicks();
    if (selection == 'H') { htries++; if (found) hhits++; }
    else { ltries++; if (found) lhits++; }
    last_type = type;
    last_bits = bits;
    last_rf = rf;
    last_error = error;
    last_search_ms = search_ms;
    if (!trace_on || (uint32_t)(now - read_at) < 500u) return;
    read_at = now;
    sprintf(line, "READ band=%c found=%d valid=%d type=0x%02X bits=%d code=%s rf=%d searchMs=%u error=0x%08X\r",
            selection, found, uid->valid, type, bits,
            uid->valid ? uid->code : "-", rf, search_ms, error);
    HostWriteString(line);
}

void d2_trace_action(D2Reader *reader, D2Stage before, D2Action action)
{
    if ((action == D2_SEND_SECOND || action == D2_END_SINGLE) && test_mode) armed = 0;
    /* Keep the first UID as the last complete line before COM handoff. */
    if (!trace_on || action == D2_NONE || action == D2_SEND_FIRST) return;
    sprintf(line, "STATE from=%s to=%s action=%s\r",
            stage_name(before), stage_name(reader->stage), action_name(action));
    HostWriteString(line);
    status(reader);
}

void d2_trace_heartbeat(D2Reader *reader, uint32_t now)
{
    if (!trace_on || reader->stage == D2_WAIT_SEND_SECOND ||
        (uint32_t)(now - heartbeat_at) < 1000u) return;
    heartbeat_at = now;
    status(reader);
}

void d2_trace_pair(const D2Reader *reader)
{
    if (!trace_on) return;
    sprintf(line, "PAIR " D2_APP_ID " HF=%s LF=%s tags=%d\r",
            reader->hf.valid ? reader->hf.code : "-",
            reader->lf.valid ? reader->lf.code : "-",
            reader->hf.valid + reader->lf.valid);
    HostWriteString(line);
}
