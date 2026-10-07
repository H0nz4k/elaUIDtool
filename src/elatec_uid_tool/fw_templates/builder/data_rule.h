#ifndef BLD_DATA_RULE_H
#define BLD_DATA_RULE_H
#include <stdint.h>
#define BLD_MAX_BITS 256
#define BLD_MAX_OUTPUT 512
typedef struct {
    int reverse_bits, reverse_bytes, first_bit, bit_count;
    int encoding, radix, length_mode, length;
    int lowercase, strip_zeros, append_00;
    const char *and_mask, *xor_mask, *separator, *prefix, *suffix;
} BldRule;
/* Input is MSB-first RAW, identical to the analyzer's byte/bit view.
 * No truncation: an oversized exact length or destination fails. */
int bld_convert(const uint8_t *raw, int bits, const BldRule *rule, char *out, int capacity);
#endif
