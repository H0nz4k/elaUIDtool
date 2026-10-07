#ifndef DUAL_CORE_H
#define DUAL_CORE_H

#include <stdint.h>

#define D2_MAX_UID_BYTES 8
#define D2_HEX_DIGITS 16
#define D2_CODE_DIGITS 20 /* Full unsigned 64-bit DEC; never a padding target. */

typedef struct {
    uint8_t seen;
    uint8_t valid;
    uint8_t bytes;
    uint8_t bits;
    uint8_t tag_type;
    uint8_t raw[D2_MAX_UID_BYTES];
    char code[D2_CODE_DIGITS + 1];
} D2Uid;

typedef struct {
    uint8_t reverse_bytes;
    uint8_t append_00;
    uint8_t radix; /* 16 = full SDK HEX, 10 = unsigned value of the same HEX. */
} D2Format;

typedef enum {
    D2_SCAN,
    D2_WAIT_HF,
    D2_WAIT_LF,
    D2_WAIT_SEND_FIRST,
    D2_WAIT_SEND_SECOND,
    D2_WAIT_REMOVE_FINAL,
    D2_LOCKED
} D2Stage;

typedef enum {
    D2_NONE,
    D2_HF_FOUND,
    D2_LF_FOUND,
    D2_SINGLE_READY,
    D2_SEND_FIRST,
    D2_SEND_SECOND,
    D2_END_SINGLE,
    D2_TIMEOUT,
    D2_READY,
    D2_INVALID_PAIR
} D2Action;

typedef struct {
    uint32_t removal_ms;
    uint32_t other_search_ms;
    uint32_t pair_timeout_ms;
    uint32_t handoff_ms;
} D2Timing;

typedef struct {
    D2Stage stage;
    D2Timing timing;
    D2Uid lf;
    D2Uid hf;
    uint32_t found_at;
    uint32_t first_sent_at;
    uint32_t absent_since;
    uint8_t absence_active;
} D2Reader;

/* sdk_hex is the full HEX string from ConvertBinaryToString, no truncation.
 * A failed conversion remains "seen" so it cannot count as card removal. */
int d2_uid_make(D2Uid *out, const uint8_t *raw, int bits,
                const char *sdk_hex, D2Format format);
int d2_uid_equal(const D2Uid *a, const D2Uid *b);
void d2_init(D2Reader *reader, D2Timing timing);
/* Scan bands separately, starting with HF; cache observations without output.
 * Once one band is found, search only the other until found or other_search_ms.
 * A dual pair is emitted HF then LF; a single UID is emitted once, followed
 * by an empty second frame to end Jidelna's two-slot registration. Found actions drive feedback only.
 * Sending uses cached codes without RF, surviving COM close/reopen and DTR.
 * A finished card stays latched until removal. Ticks wrap at 32 bits. */
D2Action d2_step(D2Reader *reader, uint32_t now,
                 const D2Uid *lf, const D2Uid *hf, int host_ready);
const char *d2_output(const D2Reader *reader, D2Action action);

#endif
