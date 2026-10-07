#include "data_rule.h"
#include <string.h>

static int nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int mask_value(const char *mask, int bit_from_right)
{
    int length = (int)strlen(mask), index = length - 1 - bit_from_right / 4;
    return index < 0 ? 0 : (nibble(mask[index]) >> (bit_from_right % 4)) & 1;
}

static int mask_fits(const char *mask, int bits)
{
    int i;
    for (i = 0; i < (int)strlen(mask); i++) if (nibble(mask[i]) < 0) return 0;
    for (i = bits; i < (int)strlen(mask) * 4; i++) if (mask_value(mask, i)) return 0;
    return 1;
}

static uint32_t low_value(const uint8_t *bits, int count)
{
    uint32_t value = 0;
    int i = count > 24 ? count - 24 : 0;
    for (; i < count; i++) value = (value << 1) | bits[i];
    return value;
}

static int structured(uint8_t *bits, int *count, int encoding)
{
    uint32_t value, facility, card, multiplier;
    int i, width = 0;
    if (encoding >= 8) {
        if (*count != 26) return -1;
        value = low_value(bits + 1, 24);
    } else value = low_value(bits, *count);
    facility = value >> 16;
    card = value & 0xFFFFu;
    switch (encoding) {
    case 1: case 8: value = facility * 100000u + card; width = 8; break;
    case 2: case 11: value = facility * 100000u + card; break;
    case 3: case 9:
        multiplier = 1;
        for (value = card; value; value /= 10) multiplier *= 10;
        value = facility * multiplier + card;
        break;
    case 4: case 10: value = card; break;
    case 5: value = facility; break;
    case 6: value = facility * 10000u + card; break;
    case 7: value = facility * 1000000u + card; break;
    default: return -1;
    }
    *count = 32;
    for (i = 0; i < 32; i++) bits[i] = (uint8_t)((value >> (31 - i)) & 1u);
    return width;
}

/* Arbitrary precision radix conversion, up to 256 bits, without float/uint64 overflow. */
static int radix_string(const uint8_t *bits, int count, int radix, char *out)
{
    static const char alphabet[] = "0123456789ABCDEF";
    uint8_t digits[BLD_MAX_BITS];
    int used = 1, i, j;
    memset(digits, 0, sizeof(digits));
    if (radix != 2 && radix != 8 && radix != 10 && radix != 16) return -1;
    for (i = 0; i < count; i++) {
        int carry = bits[i];
        for (j = 0; j < used; j++) {
            int value = digits[j] * 2 + carry;
            digits[j] = (uint8_t)(value % radix);
            carry = value / radix;
        }
        if (carry) {
            if (used >= BLD_MAX_BITS) return -1;
            digits[used++] = (uint8_t)carry;
        }
    }
    for (i = 0; i < used; i++) out[i] = alphabet[digits[used - i - 1]];
    out[used] = 0;
    return used;
}

int bld_convert(const uint8_t *raw, int bits, const BldRule *rule, char *out, int capacity)
{
    uint8_t work[BLD_MAX_BITS], temp[BLD_MAX_BITS], selected[BLD_MAX_BITS];
    char text[BLD_MAX_BITS + 3];
    int count, i, length, width = 0, required, cursor = 0;
    if (capacity > 0 && out) out[0] = 0;
    if (!raw || !rule || !out || bits < 1 || bits > BLD_MAX_BITS || capacity < 1) return 0;
    for (i = 0; i < bits; i++) work[i] = (raw[i / 8] >> (7 - i % 8)) & 1u;
    if (rule->reverse_bits) {
        for (i = 0; i < bits; i++) temp[i] = work[bits - 1 - i];
        memcpy(work, temp, (unsigned int)bits);
    }
    if (rule->reverse_bytes) {
        if (bits % 8) return 0;
        for (i = 0; i < bits; i++) temp[i] = work[(bits / 8 - 1 - i / 8) * 8 + i % 8];
        memcpy(work, temp, (unsigned int)bits);
    }
    count = rule->bit_count ? rule->bit_count : bits - rule->first_bit;
    if (rule->first_bit < 0 || count < 1 || rule->first_bit + count > bits) return 0;
    memcpy(selected, work + rule->first_bit, (unsigned int)count);
    if (!mask_fits(rule->and_mask, count) || !mask_fits(rule->xor_mask, count)) return 0;
    for (i = 0; i < count; i++) {
        if (rule->and_mask[0]) selected[i] &= mask_value(rule->and_mask, count - 1 - i);
        if (rule->xor_mask[0]) selected[i] ^= mask_value(rule->xor_mask, count - 1 - i);
    }
    if (rule->encoding) {
        width = structured(selected, &count, rule->encoding);
        if (width < 0) return 0;
    }
    if (!rule->radix) {
        if (rule->encoding || count % 8) return 0;
        length = count / 8;
        for (i = 0; i < length; i++) {
            int j, character = 0;
            for (j = 0; j < 8; j++) character = (character << 1) | selected[i * 8 + j];
            if (character < 32 || character > 126) return 0;
            text[i] = (char)character;
        }
        text[length] = 0;
        width = 0;
    } else {
        length = radix_string(selected, count, rule->radix, text);
        if (length < 1) return 0;
        if (!rule->encoding && rule->radix == 16) width = (count + 3) / 4;
        else if (rule->radix != 10) width = 0;
    }
    if (width > length) {
        memmove(text + width - length, text, (unsigned int)length + 1);
        memset(text, '0', (unsigned int)(width - length));
        length = width;
    }
    if (rule->strip_zeros) {
        i = 0;
        while (i < length - 1 && text[i] == '0') i++;
        if (i) { memmove(text, text + i, (unsigned int)(length - i + 1)); length -= i; }
    }
    if (rule->length_mode) {
        if (rule->length < 1 || rule->length > BLD_MAX_BITS) return 0;
        if (rule->length_mode == 2 && length > rule->length) return 0;
        if (length < rule->length) {
            memmove(text + rule->length - length, text, (unsigned int)length + 1);
            memset(text, rule->radix ? '0' : ' ', (unsigned int)(rule->length - length));
            length = rule->length;
        }
    }
    if (rule->append_00) { text[length++] = '0'; text[length++] = '0'; text[length] = 0; }
    if (rule->lowercase) for (i = 0; i < length; i++)
        if (text[i] >= 'A' && text[i] <= 'Z') text[i] += 'a' - 'A';
    if (rule->separator[0] && (rule->radix != 16 || length % 2)) return 0;
    required = (int)strlen(rule->prefix) + length + (int)strlen(rule->suffix);
    if (rule->separator[0]) required += length / 2 - 1;
    if (required >= capacity) return 0;
    strcpy(out, rule->prefix);
    cursor = (int)strlen(out);
    for (i = 0; i < length; i++) {
        if (rule->separator[0] && i && i % 2 == 0) out[cursor++] = rule->separator[0];
        out[cursor++] = text[i];
    }
    strcpy(out + cursor, rule->suffix);
    return 1;
}
