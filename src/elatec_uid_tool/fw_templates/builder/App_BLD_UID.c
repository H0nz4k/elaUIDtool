#include "twn4.sys.h"
#include "apptools.h"
#include "builder_config.h"
#include "data_rule.h"
#include "feedback.h"

int main(void)
{
    byte raw[32], old_raw[32];
    int old_type = -1, old_bits = 0, latched = 0, absence_active = 0;
    unsigned long absent_at = 0;
#if BLD_REPEAT_MS
    unsigned long sent_at = 0;
#endif
    unsigned int supported_lf, supported_hf;
    bld_startup();
    if (!bld_setup_host()) { bld_feedback(&BLD_ERROR); while (true) Delay(50); }
    GetSupportedTagTypes(&supported_lf, &supported_hf);
    supported_lf &= BLD_LF_MASK;
    supported_hf &= BLD_HF_MASK;
    if (!supported_lf && !supported_hf) { bld_feedback(&BLD_ERROR); while (true) Delay(50); }
    SetTagTypes(supported_lf, supported_hf);
    memset(old_raw, 0, sizeof(old_raw));
    while (true) {
        int type = 0, bits = 0, found;
        unsigned long now;
        if (!bld_host_ready()) { Delay(10); continue; }
        memset(raw, 0, sizeof(raw));
        found = SearchTag(&type, &bits, raw, sizeof(raw));
        now = GetSysTicks();
        if (found) {
            char output[BLD_MAX_OUTPUT];
            int same, repeat_due = 0;
            const BldRule *rule = type >= 0x80 ? &BLD_HF : &BLD_LF;
            unsigned int mask = type >= 0x80 ? supported_hf : supported_lf;
            absence_active = 0;
            if (bits < 1 || bits > 256 || !(mask & TAGMASK(type))) {
                if (!latched) bld_feedback(&BLD_ERROR);
                latched = 1;
                Delay(10);
                continue;
            }
            same = latched && type == old_type && bits == old_bits &&
                   memcmp(raw, old_raw, (unsigned int)((bits + 7) / 8)) == 0;
#if BLD_REPEAT_MS
            repeat_due = (unsigned long)(now - sent_at) >= BLD_REPEAT_MS;
#endif
            if (!same || repeat_due) {
                memcpy(old_raw, raw, (unsigned int)((bits + 7) / 8));
                old_bits = bits;
                old_type = type;
                latched = 1;
                if (bld_convert(raw, bits, rule, output, sizeof(output))) {
                    if (BLD_REMOTE_WAKEUP && GetUSBDeviceState() == USB_DEVICE_STATE_SUSPENDED) USBRemoteWakeup();
                    HostWriteString(output);
                    HostWriteString(BLD_TERMINATOR);
                    bld_feedback(&BLD_SUCCESS);
                } else bld_feedback(&BLD_ERROR);
#if BLD_REPEAT_MS
                sent_at = GetSysTicks();
#endif
            }
        } else if (latched) {
            if (!absence_active) { absent_at = now; absence_active = 1; }
            if ((unsigned long)(now - absent_at) >= BLD_REMOVAL_MS) {
                latched = 0;
                absence_active = 0;
                bld_idle();
            }
        }
        Delay(10);
    }
}
