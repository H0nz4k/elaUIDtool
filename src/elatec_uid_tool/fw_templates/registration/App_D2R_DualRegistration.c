/* D2R0.15: discover one/two bands without output, send cached Jidelna-compatible result.
 * Normal USB CDC output is full UID HEX/DEC + CR, never 16-digit padding.
 * Diagnostics are opt-in; no state reset on COM close/reopen or DTR. */
#include "twn4.sys.h"
#include "apptools.h"
#include "dual_core.h"
#include "dual_config.h"
#include "rf_types.h"
#include "registration_signal.h"
#include "registration_trace.h"

static D2Reader reader;
static unsigned int supported_lf, supported_hf;
static char current_band, next_scan;

static void configure_band(char selection)
{
    if (selection == current_band) return;
    SetRFOff();
    SetTagTypes(selection == 'L' ? supported_lf : NOTAG,
                selection == 'H' ? supported_hf : NOTAG);
    current_band = selection;
    d2_trace_band(selection);
    if (selection != 'P') Delay(D2_RF_PAUSE_MS);
}

static D2Uid read_one(int hf)
{
    D2Uid uid;
    D2Format format = {hf ? D2_HF_REVERSE_BYTES : D2_LF_REVERSE_BYTES,
                        hf ? D2_HF_APPEND_00 : D2_LF_APPEND_00,
                        hf ? D2_HF_RADIX : D2_LF_RADIX};
    int type = 0, bits = 0, found, rf;
    unsigned int error;
    uint32_t search_at;
    unsigned int search_ms;
    unsigned int mask = hf ? supported_hf : supported_lf;
    byte raw[32];
    char text[D2_HEX_DIGITS + 1];
    memset(&uid, 0, sizeof(uid));
    memset(raw, 0, sizeof(raw));
    memset(text, 0, sizeof(text));
    search_at = (uint32_t)GetSysTicks();
    found = SearchTag(&type, &bits, raw, sizeof(raw));
    error = GetLastError();
    rf = GetSearchTagResult();
    search_ms = (unsigned int)((uint32_t)GetSysTicks() - search_at);
    if (found) {
        uid.seen = 1;
        if (d2_type_in_band(type, mask, hf) && bits >= 1 && bits <= 64) {
            ConvertBinaryToString(raw, 0, bits, text, 16,
                                  (bits + 3) / 4, D2_HEX_DIGITS);
            text[D2_HEX_DIGITS] = 0;
            d2_uid_make(&uid, raw, bits, text, format);
            uid.tag_type = (uint8_t)type;
        }
    }
    d2_trace_read(hf ? 'H' : 'L', type, bits, found, rf, error, search_ms, &uid);
    return uid;
}

int main(void)
{
    D2Timing timing = {D2_REMOVAL_MS, D2_OTHER_SEARCH_MS, D2_PAIR_TIMEOUT_MS, D2_HANDOFF_MS};
    int channel_ok;
    d2_signal_init();
#if D2_HOST_CHANNEL == CHANNEL_COM1
    {
        TCOMParameters parameters;
        parameters.BaudRate = D2_UART_BAUD;
        parameters.WordLength = COM_WORDLENGTH_8;
        parameters.Parity = COM_PARITY_NONE;
        parameters.StopBits = COM_STOPBITS_1;
        parameters.FlowControl = COM_FLOWCONTROL_NONE;
        if (!SetCOMParameters(CHANNEL_COM1, &parameters)) {
            d2_signal_action(&reader, D2_TIMEOUT);
            while (true) Delay(50);
        }
    }
#endif
    channel_ok = SetHostChannel(D2_HOST_CHANNEL);
    d2_init(&reader, timing);
    GetSupportedTagTypes(&supported_lf, &supported_hf);
    supported_hf = d2_hf_card_types(supported_hf);
    d2_trace_init(supported_lf, supported_hf);
    current_band = '?';
    next_scan = 'H';
    if (!channel_ok || !supported_lf || !supported_hf) {
        reader.stage = D2_LOCKED;
        d2_signal_action(&reader, D2_TIMEOUT);
    }
    while (true) {
        D2Uid lf = {0}, hf = {0};
        D2Stage before;
        D2Action action;
        uint32_t now;
        const char *output;
        int host_ready;
        d2_trace_poll(&reader);
        now = (uint32_t)GetSysTicks();
        host_ready = d2_host_ready();
        if (reader.stage == D2_LOCKED ||
            (reader.stage == D2_SCAN && !host_ready)) {
            configure_band('P');
            next_scan = 'H';
            d2_trace_heartbeat(&reader, now);
            Delay(10);
            continue;
        }
        /* Sending uses cached codes and no RF call, so a slow search cannot
         * delay COM handoff. There is no removal gate between HF and LF. */
        if (reader.stage == D2_WAIT_SEND_FIRST || reader.stage == D2_WAIT_SEND_SECOND)
            configure_band('P');
        else {
            char selection;
            if (reader.stage == D2_SCAN)
                selection = next_scan;
            else if (reader.stage == D2_WAIT_HF)
                selection = 'H';
            else if (reader.stage == D2_WAIT_REMOVE_FINAL)
                selection = reader.lf.valid ? 'L' : 'H';
            else selection = 'L';
            configure_band(selection);
            if (current_band == 'H') hf = read_one(1);
            else lf = read_one(0);
            if (reader.stage == D2_SCAN) next_scan = current_band == 'H' ? 'L' : 'H';
        }
        now = (uint32_t)GetSysTicks();
        before = reader.stage;
        /* Recheck after RF: the USB/DTR state can change during SearchTag. */
        action = d2_step(&reader, now, &lf, &hf, d2_host_ready());
        if (action == D2_READY) next_scan = 'H';
        output = d2_output(&reader, action);
        if (output) {
            if (action == D2_SEND_FIRST) d2_trace_pair(&reader);
            HostWriteString(output);
            HostWriteString("\r");
        }
        d2_signal_action(&reader, action);
        d2_trace_action(&reader, before, action);
        d2_trace_heartbeat(&reader, now);
        Delay(10);
    }
}
