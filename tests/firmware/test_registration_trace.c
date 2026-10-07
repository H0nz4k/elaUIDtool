#include "twn4.sys.h"
#include "apptools.h"
#include "dual_core.h"
#include "registration_trace.h"
#include <assert.h>
#include <string.h>
int printf(const char *format, ...);
static int usb = USB_DEVICE_STATE_CONFIGURED;
static byte control;
static unsigned long ticks;
static const char *input;
static unsigned int position;
static char output[16000];
static int signal_resets;
int GetUSBDeviceState(void) { return usb; }
byte GetCDCControlLineState(void) { return control; }
unsigned long GetSysTicks(void) { return ticks; }
int GetVersionString(char *text, int max)
{ assert(max > 8); strcpy(text, "D2R0.15"); return 7; }
void d2_signal_init(void) { signal_resets++; }
void HostWriteString(const char *text)
{ assert(strlen(output) + strlen(text) < sizeof(output)); strcat(output, text); }
bool HostTestByte(void) { return input && input[position]; }
byte HostReadByte(void) { return (byte)input[position++]; }
static void send(D2Reader *r, const char *text)
{ input = text; position = 0; output[0] = 0; d2_trace_poll(r); }

int main(void)
{
    D2Reader r;
    D2Timing timing = {300, 2000, 30000, 200};
    d2_init(&r, timing);
    d2_trace_init(1, 1);
    assert(d2_host_ready());
    send(&r, "T\rN\rG\r!N\r");
    assert(strstr(output, "DENIED N") && signal_resets == 0);
    send(&r, "!T\r");
    assert(strstr(output, "ACK T") && !d2_host_ready());
    control = CDC_CONTROL_LINE_STATE_DTR;
    assert(!d2_host_ready());
    send(&r, "!N\r");
    assert(strstr(output, "ACK N") && signal_resets == 1);
    send(&r, "!G\r");
    assert(strstr(output, "ACK G") && d2_host_ready());
    r.stage = D2_WAIT_LF; r.first_sent_at = 123; r.hf.valid = 1;
    control = 0;
    assert(!d2_host_ready() && r.stage == D2_WAIT_LF);
    usb = USB_DEVICE_STATE_ADDRESSED;
    assert(!d2_host_ready());
    usb = USB_DEVICE_STATE_CONFIGURED; control = CDC_CONTROL_LINE_STATE_DTR;
    assert(d2_host_ready() && r.first_sent_at == 123 && r.hf.valid);
    send(&r, "!N\r");
    assert(strstr(output, "DENIED N") && r.hf.valid && signal_resets == 1);
    r.stage = D2_LOCKED;
    send(&r, "!S\r");
    assert(strstr(output, "stage=LOCKED") && strstr(output, "searchMs="));
    send(&r, "!P\r!N\r");
    assert(strstr(output, "ACK P") && strstr(output, "ACK N"));
    assert(r.stage == D2_SCAN && !r.hf.valid && signal_resets == 2);
    send(&r, "!G\r");
    assert(d2_host_ready());
    d2_trace_action(&r, D2_WAIT_SEND_SECOND, D2_SEND_SECOND);
    assert(!d2_host_ready());
    r.stage = D2_WAIT_SEND_SECOND; r.hf.valid = 1;
    send(&r, "!Q\r");
    control = 0;
    assert(d2_host_ready() && r.stage == D2_WAIT_SEND_SECOND && r.hf.valid);
    output[0] = 0; ticks = 2000;
    d2_trace_heartbeat(&r, (uint32_t)ticks);
    assert(!*output);
    d2_trace_init(1, 0); r.stage = D2_LOCKED;
    send(&r, "!T\r!N\r");
    assert(strstr(output, "DENIED N") && r.stage == D2_LOCKED);
    printf("PASS: test-session gating, denied reset, COM reopen, locked reset, raw-only restore\n");
    return 0;
}
