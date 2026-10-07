/* Real SDK declarations with mocked RF, USB, LED and sound. No physical RF claim. */
#include "twn4.sys.h"
#include "apptools.h"
#include "dual_config.h"
#include "dual_core.h"
#include <assert.h>
#include <setjmp.h>
#include <string.h>

int d2_app_main(void);
int printf(const char *format, ...);
static jmp_buf finished;
static const char *scenario;
static unsigned long ticks, sent_at[100], green_at, beep_at, off_at;
static unsigned int lf_mask, hf_mask;
static int hf_capture_frame = -1;
static int frames, rf_off, searches, hsearches, lsearches, lights, beep_on;
static int pulses, off_pending, lows, trace_stage, ready_count, lf_captures;
static int ack_t, ack_n, ack_g, ack_q, denied_n, statuses, state_h, state_l;
static char received[100][D2_CODE_DIGITS + 1], out_line[600], input[100];
static unsigned int out_length, input_at, input_length;
#define LF_TYPES (TAGMASK(LFTAG_EM4102) | TAGMASK(LFTAG_HITAG1S) | TAGMASK(LFTAG_HIDPROX))
#define HF_TYPES (TAGMASK(HFTAG_MIFARE) | TAGMASK(HFTAG_ISO14443B) | TAGMASK(HFTAG_ISO15693))
#define NON_CARD_TYPES (TAGMASK(HFTAG_BLE) | TAGMASK(HFTAG_BLELC) | TAGMASK(HFTAG_NFCP2P))
static int is(const char *name) { return strcmp(scenario, name) == 0; }
static int single(void) { return is("missing-hf") || is("missing-lf"); }
static int complete(void)
{
    return is("repeat") || is("extended") || is("dropout") ||
        is("trace") || is("lf-once") || is("slow-search") || single();
}
static int expected_frames(void) { return (is("trace") || is("lf-once")) ? 2 : (is("slow-search") ? 20 : 100); }
static unsigned long since_code(void) { return frames ? ticks - sent_at[frames - 1] : ticks; }
static void stop_if_done(void)
{
    if ((complete() && frames == expected_frames() && since_code() >= 1200) ||
        (!complete() && ticks >= (is("no-band") || is("paused") ? 2000u : 35000u)))
        longjmp(finished, 1);
    assert(ticks < 300000u);
}
void LEDInit(int leds) { assert(leds == (REDLED | GREENLED)); lights = 0; }
void LEDOn(int leds)
{
    lights |= leds;
    if (leds & GREENLED) green_at = ticks;
    if (leds & REDLED) assert(!beep_on);
}
void LEDOff(int leds)
{
    if (off_pending) {
        assert((leds & GREENLED) && ticks == off_at);
        off_pending = 0;
    }
    lights &= ~leds;
}
void SetVolume(int volume) { assert(volume == 100); }
void BeepOn(int volume, int frequency)
{
    assert(volume == 100 && frequency == 4000 && !beep_on);
    assert((lights & GREENLED) && !(lights & REDLED) && green_at == ticks);
    assert(frames % 2 == 0); /* both findings signalled BEFORE any output */
    if (pulses % (single() ? 1 : 2)) assert(ticks - off_at == 60);
    beep_on = 1; beep_at = ticks; pulses++;
}
void BeepOff(void)
{
    if (beep_on) {
        assert((lights & GREENLED) && ticks - beep_at == 60);
        off_at = ticks; off_pending = 1;
    }
    beep_on = 0;
}
void BeepLow(void) { assert(!beep_on); lows++; }
bool SetHostChannel(int channel) { assert(channel == CHANNEL_USB); return true; }
int GetUSBDeviceState(void)
{
    if (is("host-down") && ticks >= 200) return USB_DEVICE_STATE_ADDRESSED;
    if (frames % 2 && since_code() < 500) return USB_DEVICE_STATE_ADDRESSED;
    return USB_DEVICE_STATE_CONFIGURED;
}
byte GetCDCControlLineState(void)
{
    /* Jidelna's normal mode does not require DTR. Test sessions do. */
    if (!is("trace") && !is("paused")) return 0;
    if (frames % 2 && since_code() < 700) return 0;
    return CDC_CONTROL_LINE_STATE_DTR;
}
int GetVersionString(char *text, int max)
{
    const char *version = "TWN4/B1.64/NCF5.20/D2R0.15";
    assert(max >= (int)strlen(version)); strcpy(text, version);
    return (int)strlen(text);
}
unsigned int GetLastError(void) { return 0x10000001u; }
int GetSearchTagResult(void) { return STR_TAG_FOUND; }
void GetSupportedTagTypes(unsigned int *lf, unsigned int *hf)
{
    *lf = LF_TYPES; *hf = is("no-band") ? NON_CARD_TYPES : HF_TYPES | NON_CARD_TYPES;
}
void SetRFOff(void) { rf_off = 1; }
void SetTagTypes(unsigned int lf, unsigned int hf)
{
    assert(rf_off && !beep_on); rf_off = 0;
    assert((lf == LF_TYPES && hf == 0) || (lf == 0 && hf == HF_TYPES) ||
           (lf == 0 && hf == 0));
    lf_mask = lf; hf_mask = hf;
}
void Delay(unsigned long duration)
{
    assert(duration == 100 || duration == 10 || duration == 50 || duration == 60);
    ticks += duration; stop_if_done();
}
unsigned long GetSysTicks(void) { stop_if_done(); return ticks; }

static int card_present(void)
{
    unsigned long elapsed = since_code();
    if (!frames || frames % 2) return 1; /* same presentation for BOTH tags */
    if (is("lf-once") || (frames == expected_frames() && elapsed >= 400)) return 0;
    if (elapsed < 400) return 1; /* hold completed card: no repeat output */
    return elapsed < (is("slow-search") ? 3000u : 1000u) ? 0 : 1;
}

bool SearchTag(int *type, int *bits, byte *id, int max_bytes)
{
    const byte em[] = {1, 2, 3, 4, 5};
    const byte mf[] = {0x11, 0x22, 0x33, 0x44};
    const byte prox[] = {1, 0x23, 0x45, 0x67};
    const byte iso[] = {1, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef};
    int present = card_present(), hf = hf_mask != 0;
    assert(max_bytes == 32 && !off_pending && !beep_on);
    assert((lf_mask == LF_TYPES) != (hf_mask == HF_TYPES));
    if (is("trace")) assert(ticks >= 300);
    if (hf) {
        assert(frames % 2 == 0);
        if (!single()) assert(hf_capture_frame != frames); /* no HF after its capture */
        hsearches++;
    } else {
        lsearches++;
    }
    searches++; ticks += is("slow-search") ? 800 : 40; stop_if_done();
    if (!present || (is("dropout") && searches % 2 == 0)) return false;
    if (hf && is("missing-hf")) return false;
    if (!hf && is("missing-lf")) return false;
    if (hf) {
        *type = is("extended") ? HFTAG_ISO15693 : HFTAG_MIFARE;
        *bits = is("extended") ? 64 : 32;
        memcpy(id, is("extended") ? iso : mf, is("extended") ? sizeof(iso) : sizeof(mf));
        if (is("oversize")) { *bits = 80; id[9] = 1; }
        if (is("zero")) memset(id, 0, 4);
        if (!is("oversize") && !is("zero")) hf_capture_frame = frames;
    } else {
        if (is("lf-once") && lf_captures) return false;
        *type = is("extended") ? LFTAG_HIDPROX : LFTAG_EM4102;
        *bits = is("extended") ? 26 : 40;
        memcpy(id, is("extended") ? prox : em, is("extended") ? sizeof(prox) : sizeof(em));
        if (is("collision")) { id[0] = 0; memcpy(id + 1, mf, sizeof(mf)); }
        if (lf_captures == frames / 2 && frames % 2 == 0 &&
            (!frames || since_code() >= 1000)) lf_captures++;
    }
    return true;
}
int ConvertBinaryToString(const byte *source, int start, int bits, char *text,
                          int radix, int min_digits, int max_digits)
{
    static const char digits[] = "0123456789ABCDEF";
    char bytes_hex[17];
    int i, bytes = (bits + 7) / 8, width = (bits + 3) / 4;
    assert(start == 0 && radix == 16 && min_digits == width && max_digits == 16);
    assert(bits > 0 && bits <= 64);
    for (i = 0; i < bytes; i++) {
        bytes_hex[i * 2] = digits[source[i] >> 4];
        bytes_hex[i * 2 + 1] = digits[source[i] & 15];
    }
    bytes_hex[bytes * 2] = 0;
    strcpy(text, bytes_hex + bytes * 2 - width);
    return width;
}
static int hex_line(const char *text)
{
    const char *p = text;
    if (!*p || strlen(p) > D2_CODE_DIGITS) return 0;
    while (*p) {
        if (!(*p >= '0' && *p <= '9') && !(*p >= 'A' && *p <= 'F')) return 0;
        p++;
    }
    return 1;
}
static void received_line(const char *text)
{
    if (hex_line(text) || !*text) {
        assert(frames < 100 && !beep_on);
        if (!is("missing-lf")) assert(lf_captures == frames / 2 + 1);
        assert(pulses == (frames / 2 + 1) * (single() ? 1 : 2));
        assert(!single() || frames % 2 == 0 || !*text);
        if (frames % 2) assert(since_code() >= (is("trace") ? 700u : 500u));
        strcpy(received[frames], text); sent_at[frames++] = ticks;
    } else {
        assert(is("trace") || is("paused"));
        if (strcmp(text, "ACK T D2R0.15") == 0) ack_t++;
        if (strcmp(text, "ACK N D2R0.15") == 0) ack_n++;
        if (strcmp(text, "ACK G D2R0.15") == 0) ack_g++;
        if (strcmp(text, "ACK Q D2R0.15") == 0) ack_q++;
        if (strcmp(text, "DENIED N D2R0.15") == 0) denied_n++;
        if (strstr(text, "STATUS D2R0.15")) statuses++;
        if (strstr(text, "action=SEND_FIRST")) state_h++;
        if (strstr(text, "action=SEND_SECOND")) state_l++;
        if (strstr(text, "action=READY")) ready_count++;
    }
}
void HostWriteString(const char *text)
{
    while (*text) {
        if (*text == '\r') {
            out_line[out_length] = 0; received_line(out_line); out_length = 0;
        } else {
            assert(*text != '\n' && out_length < sizeof(out_line) - 1);
            out_line[out_length++] = *text;
        }
        text++;
    }
}
static void queue(const char *text)
{
    assert(input_at == input_length);
    strcpy(input, text); input_at = 0; input_length = (unsigned int)strlen(text);
}
bool HostTestByte(void)
{
    if (!is("trace") && !is("paused")) return false;
    if (input_at < input_length) return true;
    if (trace_stage == 0) { queue("xT\r!T\r!N\r"); trace_stage = 1; }
    else if (is("trace") && trace_stage == 1 && ticks >= 300) { queue("!G\r"); trace_stage = 2; }
    else if (trace_stage == 2 && frames == 1 && since_code() >= 100) {
        queue("!N\r!S\r"); trace_stage = 3;
    } else if (trace_stage == 3 && state_l == 1) {
        queue("!Q\r"); trace_stage = 4;
    }
    return input_at < input_length;
}
byte HostReadByte(void) { assert(input_at < input_length); return (byte)input[input_at++]; }

int main(int argc, char **argv)
{
    int i;
    assert(argc == 2); scenario = argv[1];
    if (setjmp(finished) == 0) d2_app_main();
    assert(!out_length && !beep_on && !off_pending);
    if (complete()) {
        assert(frames == expected_frames() && pulses == frames / 2 * (single() ? 1 : 2) && lows == 0);
        assert((lights & GREENLED) && !(lights & REDLED));
        for (i = 0; i < frames; i += 2) {
            const char *hf = D2_HF_RADIX == 16 ? "11223344" : "287454020";
            const char *lf = D2_LF_RADIX == 16 ? "0102030405" : "4328719365";
            const char *hf64 = D2_HF_RADIX == 16 ? "0123456789ABCDEF" : "81985529216486895";
            const char *lf26 = D2_LF_RADIX == 16 ? "1234567" : "19088743";
            assert(strcmp(received[i], is("extended") ? hf64 : (is("missing-hf") ? lf : hf)) == 0);
            assert(strcmp(received[i + 1], is("extended") ? lf26 : (single() ? "" : lf)) == 0);
            assert(sent_at[i + 1] - sent_at[i] >= (is("trace") ? 700u : 500u));
        }
        if (is("trace")) {
            assert(ack_t == 1 && ack_n == 1 && ack_g == 1 && ack_q == 1 && denied_n == 1);
            assert(state_h == 0 && state_l == 1 && statuses >= 4);
        }
    } else if (is("host-down") || is("collision")) {
        assert(frames == 0 && pulses == (is("host-down") ? 2 : 0));
        assert((lights & REDLED) && !(lights & GREENLED));
    } else {
        assert(frames == 0 && pulses == 0);
        if (is("no-band")) assert(searches == 0 && (lights & REDLED));
        
        if (is("paused")) assert(searches == 0 && ack_g == 0);
    }
    printf("PASS: SDK registration %s, %d frames, %d synchronized loud pulses\n", scenario, frames, pulses);
    return 0;
}
