#include "dual_core.h"
#include <string.h>

static int hex_digit(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

int d2_uid_make(D2Uid *out, const uint8_t *raw, int bits,
                const char *sdk_hex, D2Format format)
{
    static const char digits[] = "0123456789ABCDEF";
    char hex[D2_HEX_DIGITS + 1];
    uint64_t value = 0;
    int n, digits_count, i, length, nonzero = 0, text_nonzero = 0;
    memset(out, 0, sizeof(*out));
    out->seen = 1;
    if (!raw || !sdk_hex || bits < 1 || bits > 64) return 0;
    n = (bits + 7) / 8;
    digits_count = (bits + 3) / 4;
    if (format.reverse_bytes > 1 || format.append_00 > 1) return 0;
    if (format.radix != 10 && format.radix != 16) return 0;
    if (format.reverse_bytes && (bits % 8)) return 0;
    if (digits_count + format.append_00 * 2 > D2_HEX_DIGITS) return 0;
    for (i = 0; i < n; i++) nonzero |= raw[i];
    if (!nonzero) return 0;
    for (i = 0; i < digits_count; i++) {
        int digit = hex_digit(sdk_hex[i]);
        if (digit < 0) return 0;
        text_nonzero |= digit;
    }
    if (!text_nonzero || sdk_hex[digits_count] != '\0') return 0;
    for (i = 0; i < digits_count; i++) {
        int src = format.reverse_bytes ? (n - i / 2 - 1) * 2 + i % 2 : i;
        hex[i] = digits[hex_digit(sdk_hex[src])];
    }
    length = digits_count;
    if (format.append_00) {
        hex[length++] = '0';
        hex[length++] = '0';
    }
    hex[length] = '\0';
    if (format.radix == 16) memcpy(out->code, hex, (unsigned int)length + 1);
    else {
        char decimal[D2_CODE_DIGITS];
        int count = 0;
        /* Convert SDK's canonical string, never reinterpret raw SDK byte order.
         * Avoid floating point and 32-bit intermediate values. */
        for (i = 0; i < length; i++) value = (value << 4) | (unsigned int)hex_digit(hex[i]);
        do {
            decimal[count++] = (char)('0' + value % 10u);
            value /= 10u;
        } while (value);
        for (i = 0; i < count; i++) out->code[i] = decimal[count - i - 1];
        out->code[count] = '\0';
    }
    memcpy(out->raw, raw, (unsigned int)n);
    out->bytes = (uint8_t)n;
    out->bits = (uint8_t)bits;
    out->valid = 1;
    return 1;
}

int d2_uid_equal(const D2Uid *a, const D2Uid *b)
{
    return a->valid && b->valid && a->bytes == b->bytes &&
           a->bits == b->bits && a->tag_type == b->tag_type &&
           memcmp(a->raw, b->raw, a->bytes) == 0;
}

void d2_init(D2Reader *reader, D2Timing timing)
{
    const uint32_t values[] = {timing.removal_ms, timing.other_search_ms, timing.pair_timeout_ms, timing.handoff_ms};
    unsigned int i;
    memset(reader, 0, sizeof(*reader));
    reader->timing = timing;
    reader->stage = D2_SCAN;
    for (i = 0; i < sizeof(values) / sizeof(values[0]); i++)
        if (values[i] == 0 || values[i] > 0x7FFFFFFFu) reader->stage = D2_LOCKED;
}

static int elapsed(uint32_t now, uint32_t start, uint32_t duration)
{
    return (uint32_t)(now - start) >= duration;
}

/* Jidelna left-pads itself; compare collisions without changing output. */
static int same_jidelna_number(const char *a, const char *b)
{
    while (*a == '0') a++;
    while (*b == '0') b++;
    return strcmp(a, b) == 0;
}

static int removed(D2Reader *r, uint32_t now, int present)
{
    if (present) {
        r->absence_active = 0;
        return 0;
    }
    if (!r->absence_active) {
        r->absent_since = now;
        r->absence_active = 1;
    }
    return elapsed(now, r->absent_since, r->timing.removal_ms);
}

static D2Action found(D2Reader *r, uint32_t now, const D2Uid *uid, int hf)
{
    if (!uid->valid) {
        r->stage = D2_LOCKED;
        return D2_INVALID_PAIR;
    }
    if (hf) r->hf = *uid;
    else r->lf = *uid;
    if (r->hf.valid && r->lf.valid) {
        if (same_jidelna_number(r->hf.code, r->lf.code)) {
            r->stage = D2_LOCKED;
            return D2_INVALID_PAIR;
        }
        r->stage = D2_WAIT_SEND_FIRST;
    } else {
        r->found_at = now;
        r->stage = hf ? D2_WAIT_LF : D2_WAIT_HF;
    }
    return hf ? D2_HF_FOUND : D2_LF_FOUND;
}

D2Action d2_step(D2Reader *r, uint32_t now,
                 const D2Uid *lf, const D2Uid *hf, int host_ready)
{
    if (r->stage == D2_LOCKED) return D2_NONE;
    if ((r->stage == D2_WAIT_SEND_FIRST || r->stage == D2_WAIT_SEND_SECOND) &&
        elapsed(now, r->found_at, r->timing.pair_timeout_ms)) {
        r->stage = D2_LOCKED;
        return D2_TIMEOUT;
    }
    switch (r->stage) {
    case D2_SCAN:
        if (!host_ready) return D2_NONE;
        if (hf->seen) return found(r, now, hf, 1);
        if (lf->seen) return found(r, now, lf, 0);
        return D2_NONE;
    case D2_WAIT_HF:
    case D2_WAIT_LF:
        /* A successfully read second tag wins over the time boundary.
         * An unreadable tag is an error, not a proof of a single-tag card. */
        if (r->stage == D2_WAIT_HF && hf->seen) return found(r, now, hf, 1);
        if (r->stage == D2_WAIT_LF && lf->seen) return found(r, now, lf, 0);
        if (!elapsed(now, r->found_at, r->timing.other_search_ms)) return D2_NONE;
        r->stage = D2_WAIT_SEND_FIRST;
        return D2_SINGLE_READY;
    case D2_WAIT_SEND_FIRST:
        if (!host_ready) return D2_NONE;
        r->first_sent_at = now;
        r->stage = D2_WAIT_SEND_SECOND;
        return D2_SEND_FIRST;
    case D2_WAIT_SEND_SECOND:
        if (!host_ready || !elapsed(now, r->first_sent_at, r->timing.handoff_ms))
            return D2_NONE;
        r->stage = D2_WAIT_REMOVE_FINAL;
        r->absence_active = 0;
        return r->hf.valid && r->lf.valid ? D2_SEND_SECOND : D2_END_SINGLE;
    case D2_WAIT_REMOVE_FINAL:
        if (!removed(r, now, r->lf.valid ? lf->seen : hf->seen)) return D2_NONE;
        d2_init(r, r->timing);
        return D2_READY;
    case D2_LOCKED:
        break;
    }
    return D2_NONE;
}

const char *d2_output(const D2Reader *reader, D2Action action)
{
    if (action == D2_SEND_FIRST && reader->stage == D2_WAIT_SEND_SECOND)
        return reader->hf.valid ? reader->hf.code : (reader->lf.valid ? reader->lf.code : 0);
    if (action == D2_SEND_SECOND && reader->stage == D2_WAIT_REMOVE_FINAL &&
        reader->hf.valid && reader->lf.valid) return reader->lf.code;
    if (action == D2_END_SINGLE && reader->stage == D2_WAIT_REMOVE_FINAL &&
        (reader->hf.valid != reader->lf.valid)) return "";
    return 0;
}
