#include "dual_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned int checks;
#define CHECK(x) do { checks++; assert(x); } while (0)
static const D2Timing timing = {300, 2000, 30000, 200};
static D2Uid no_tag, lf, hf;

static D2Uid uid(const uint8_t *raw, int bits, const char *hex, int type)
{
    D2Uid out;
    D2Format format = {0, 0, 16};
    CHECK(d2_uid_make(&out, raw, bits, hex, format));
    out.tag_type = (uint8_t)type;
    return out;
}

static void test_format(void)
{
    uint8_t raw[10] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    D2Uid u;
    D2Format normal = {0, 0, 16}, reverse = {1, 0, 16}, append = {0, 1, 16};
    CHECK(d2_uid_make(&u, raw, 32, "a1b2c3d4", normal));
    CHECK(strcmp(u.code, "A1B2C3D4") == 0);
    CHECK(strlen(u.code) == 8);
    CHECK(d2_uid_make(&u, raw, 32, "A1B2C3D4", reverse));
    CHECK(strcmp(u.code, "D4C3B2A1") == 0);
    CHECK(d2_uid_make(&u, raw, 32, "A1B2C3D4", append));
    CHECK(strcmp(u.code, "A1B2C3D400") == 0);
    CHECK(d2_uid_make(&u, raw, 56, "01020304050607", normal));
    CHECK(strcmp(u.code, "01020304050607") == 0);
    CHECK(strlen(u.code) == 14);
    CHECK(d2_uid_make(&u, raw, 64, "0102030405060708", normal));
    CHECK(!d2_uid_make(&u, raw, 64, "0102030405060708", append));
    CHECK(u.seen && !u.valid);
    CHECK(!d2_uid_make(&u, raw, 80, "0102030405060708090A", normal));
    CHECK(d2_uid_make(&u, raw, 39, "0102030405", normal));
    CHECK(u.bits == 39 && u.bytes == 5);
    CHECK(!d2_uid_make(&u, raw, 39, "0102030405", reverse));
    CHECK(d2_uid_make(&u, raw, 26, "1234567", normal));
    CHECK(strcmp(u.code, "1234567") == 0 && u.bits == 26);
    CHECK(d2_uid_make(&u, raw, 1, "1", normal));
    CHECK(strcmp(u.code, "1") == 0);
    CHECK(!d2_uid_make(&u, raw, 0, "", normal));
    CHECK(!d2_uid_make(&u, raw, 32, "12", normal));
    CHECK(!d2_uid_make(&u, raw, 32, "0102030400", normal));
    CHECK(!d2_uid_make(&u, raw, 32, "01GG0304", normal));
    CHECK(!d2_uid_make(&u, raw, 32, "00000000", normal));
    memset(raw, 0, sizeof(raw));
    CHECK(!d2_uid_make(&u, raw, 32, "01020304", normal));
    CHECK(u.seen && !u.valid);
}

static void test_decimal_and_mixed_formats(void)
{
    uint8_t raw[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    D2Uid u, h, l;
    D2Format decimal = {0, 0, 10}, reverse = {1, 0, 10}, hex = {0, 0, 16};
    D2Reader reader;
    int hr, lr;
    CHECK(d2_uid_make(&u, raw, 64, "FFFFFFFFFFFFFFFF", decimal));
    CHECK(strcmp(u.code, "18446744073709551615") == 0);
    CHECK(d2_uid_make(&u, raw, 56, "FFFFFFFFFFFFFF", decimal));
    CHECK(strcmp(u.code, "72057594037927935") == 0);
    CHECK(d2_uid_make(&u, raw, 64, "0000000000000001", decimal));
    CHECK(strcmp(u.code, "1") == 0);
    CHECK(d2_uid_make(&u, raw, 32, "00112233", decimal));
    CHECK(strcmp(u.code, "1122867") == 0);
    CHECK(d2_uid_make(&u, raw, 32, "00112233", hex));
    CHECK(strcmp(u.code, "00112233") == 0);
    CHECK(d2_uid_make(&u, raw, 32, "11223344", reverse));
    CHECK(strcmp(u.code, "1144201745") == 0);
    CHECK(d2_uid_make(&u, raw, 26, "1234567", decimal));
    CHECK(strcmp(u.code, "19088743") == 0);
    decimal.radix = 8;
    CHECK(!d2_uid_make(&u, raw, 32, "11223344", decimal));
    for (hr = 10; hr <= 16; hr += 6) for (lr = 10; lr <= 16; lr += 6) {
        D2Format hfmt = {0, 0, (uint8_t)hr}, lfmt = {0, 0, (uint8_t)lr};
        CHECK(d2_uid_make(&h, raw, 32, "11223344", hfmt));
        CHECK(d2_uid_make(&l, raw, 40, "0102030405", lfmt));
        d2_init(&reader, timing);
        CHECK(d2_step(&reader, 0, &no_tag, &h, 1) == D2_HF_FOUND);
        CHECK(d2_step(&reader, 100, &l, &no_tag, 1) == D2_LF_FOUND);
        CHECK(d2_step(&reader, 110, &no_tag, &no_tag, 1) == D2_SEND_FIRST);
        CHECK(strcmp(d2_output(&reader, D2_SEND_FIRST), hr == 16 ? "11223344" : "287454020") == 0);
        CHECK(d2_step(&reader, 310, &no_tag, &no_tag, 1) == D2_SEND_SECOND);
        CHECK(strcmp(d2_output(&reader, D2_SEND_SECOND), lr == 16 ? "0102030405" : "4328719365") == 0);
    }
    /* Mixed representations can collide in Jidelna's string field. */
    decimal.radix = 10;
    CHECK(d2_uid_make(&h, raw, 32, "0000007B", decimal));
    CHECK(d2_uid_make(&l, raw, 32, "00000123", hex));
    d2_init(&reader, timing);
    CHECK(d2_step(&reader, 0, &no_tag, &h, 1) == D2_HF_FOUND);
    CHECK(d2_step(&reader, 100, &l, &no_tag, 1) == D2_INVALID_PAIR);
    CHECK(d2_output(&reader, D2_SEND_FIRST) == 0);
}


static void collect(D2Reader *r, uint32_t at, int lf_host)
{
    CHECK(d2_step(r, at, &no_tag, &hf, 1) == D2_HF_FOUND);
    CHECK(r->stage == D2_WAIT_LF && !r->lf.valid);
    CHECK(d2_output(r, D2_HF_FOUND) == 0);
    CHECK(d2_output(r, D2_SEND_FIRST) == 0); /* incomplete pair cannot escape */
    CHECK(d2_step(r, at + 10, &lf, &no_tag, lf_host) == D2_LF_FOUND);
    CHECK(r->stage == D2_WAIT_SEND_FIRST && d2_uid_equal(&r->lf, &lf));
    CHECK(d2_output(r, D2_LF_FOUND) == 0);
}

static void send_pair(D2Reader *r, uint32_t at)
{
    CHECK(d2_step(r, at, &no_tag, &no_tag, 1) == D2_SEND_FIRST);
    CHECK(strcmp(d2_output(r, D2_SEND_FIRST), "11223344") == 0);
    CHECK(d2_step(r, at + 199, &no_tag, &no_tag, 1) == D2_NONE);
    CHECK(d2_step(r, at + 200, &no_tag, &no_tag, 1) == D2_SEND_SECOND);
    CHECK(strcmp(d2_output(r, D2_SEND_SECOND), "0102030405") == 0);
    CHECK(r->stage == D2_WAIT_REMOVE_FINAL);
}

static void test_single_presentation_and_host_handoff(void)
{
    D2Reader r;
    D2Uid changed = lf;
    uint32_t t;
    changed.raw[0]++;
    d2_init(&r, timing);
    CHECK(d2_step(&r, 10, &no_tag, &hf, 0) == D2_NONE); /* not armed */
    collect(&r, 20, 0); /* LF captured even if host closes before it */
    CHECK(d2_step(&r, 40, &changed, &hf, 0) == D2_NONE);
    CHECK(d2_uid_equal(&r.lf, &lf)); /* immutable cached pair */
    CHECK(d2_step(&r, 50, &no_tag, &no_tag, 1) == D2_SEND_FIRST);
    for (t = 60; t <= 700; t += 20)
        CHECK(d2_step(&r, t, &changed, &hf, 0) == D2_NONE);
    CHECK(d2_step(&r, 720, &no_tag, &no_tag, 1) == D2_SEND_SECOND);
    CHECK(d2_uid_equal(&r.lf, &lf) && d2_uid_equal(&r.hf, &hf));
    for (t = 730; t < 5000; t += 50) {
        CHECK(d2_step(&r, t, &lf, &hf, 1) == D2_NONE);
        CHECK(r.stage == D2_WAIT_REMOVE_FINAL); /* held card never repeats */
    }
    CHECK(d2_step(&r, 5000, &no_tag, &no_tag, 1) == D2_NONE);
    CHECK(d2_step(&r, 5299, &lf, &no_tag, 1) == D2_NONE); /* cancels absence */
    CHECK(d2_step(&r, 5400, &no_tag, &no_tag, 1) == D2_NONE);
    CHECK(d2_step(&r, 5700, &no_tag, &no_tag, 1) == D2_READY);
    CHECK(r.stage == D2_SCAN && !r.lf.valid && !r.hf.valid);
}

static void test_single_cards_and_invalid(void)
{
    D2Reader r;
    D2Uid malformed = {0};
    const uint8_t same[] = {0, 0x11, 0x22, 0x33, 0x44};
    D2Uid collision = uid(same, 40, "0011223344", 0x40);
    unsigned int band;
    malformed.seen = 1;
    for (band = 0; band < 2; band++) {
        const D2Uid *only = band ? &hf : &lf;
        d2_init(&r, timing);
        CHECK(d2_step(&r, 100, band ? &no_tag : &lf, band ? &hf : &no_tag, 1) ==
              (band ? D2_HF_FOUND : D2_LF_FOUND));
        CHECK(d2_output(&r, D2_SEND_FIRST) == 0);
        CHECK(d2_step(&r, 2099, &no_tag, &no_tag, 1) == D2_NONE);
        CHECK(d2_step(&r, 2100, &no_tag, &no_tag, 1) == D2_SINGLE_READY);
        CHECK(d2_step(&r, 2110, &no_tag, &no_tag, 1) == D2_SEND_FIRST);
        CHECK(strcmp(d2_output(&r, D2_SEND_FIRST), only->code) == 0);
        CHECK(d2_step(&r, 2310, &no_tag, &no_tag, 1) == D2_END_SINGLE);
        CHECK(strcmp(d2_output(&r, D2_END_SINGLE), "") == 0);
        CHECK(d2_output(&r, D2_SEND_SECOND) == 0);
        CHECK(d2_step(&r, 2400, band ? &no_tag : &lf, band ? &hf : &no_tag, 1) == D2_NONE);
        CHECK(d2_step(&r, 2800, band ? &no_tag : &lf, band ? &hf : &no_tag, 1) == D2_NONE);
        CHECK(r.stage == D2_WAIT_REMOVE_FINAL);
        CHECK(d2_step(&r, 3000, &no_tag, &no_tag, 1) == D2_NONE);
        CHECK(d2_step(&r, 3300, &no_tag, &no_tag, 1) == D2_READY);
    }
    /* LF may be found before a weak HF; output priority stays HF -> LF. */
    d2_init(&r, timing);
    CHECK(d2_step(&r, 0, &lf, &no_tag, 1) == D2_LF_FOUND);
    CHECK(d2_step(&r, 2500, &no_tag, &hf, 1) == D2_HF_FOUND);
    send_pair(&r, 2510); /* successful final search wins over its deadline */
    d2_init(&r, timing);
    CHECK(d2_step(&r, 0, &no_tag, &malformed, 1) == D2_INVALID_PAIR);
    CHECK(r.stage == D2_LOCKED && !r.hf.valid);
    d2_init(&r, timing);
    CHECK(d2_step(&r, 0, &no_tag, &hf, 1) == D2_HF_FOUND);
    CHECK(d2_step(&r, 30, &malformed, &no_tag, 1) == D2_INVALID_PAIR);
    CHECK(r.stage == D2_LOCKED && !r.lf.valid);
    d2_init(&r, timing);
    CHECK(d2_step(&r, 0, &no_tag, &hf, 1) == D2_HF_FOUND);
    CHECK(d2_step(&r, 10, &collision, &no_tag, 1) == D2_INVALID_PAIR);
    CHECK(r.stage == D2_LOCKED && d2_output(&r, D2_SEND_FIRST) == 0);
    CHECK(strcmp(collision.code, "0011223344") == 0);
    d2_init(&r, timing); collect(&r, 0, 0);
    CHECK(d2_step(&r, 29999, &no_tag, &no_tag, 0) == D2_NONE);
    CHECK(d2_step(&r, 30000, &no_tag, &no_tag, 1) == D2_TIMEOUT);
    CHECK(d2_step(&r, 60000, &lf, &hf, 1) == D2_NONE);
    d2_init(&r, timing); collect(&r, 0, 1);
    CHECK(d2_step(&r, 20, &no_tag, &no_tag, 1) == D2_SEND_FIRST);
    CHECK(d2_step(&r, 30000, &no_tag, &no_tag, 0) == D2_TIMEOUT);
}

static void test_repeat_and_wrapping(void)
{
    D2Reader r;
    uint32_t start = UINT32_MAX - 400u;
    unsigned int pair;
    d2_init(&r, timing);
    for (pair = 0; pair < 100; pair++) {
        uint32_t at = start + pair * 2000u;
        collect(&r, at, 1);
        send_pair(&r, at + 20);
        CHECK(d2_step(&r, at + 300, &lf, &no_tag, 1) == D2_NONE);
        CHECK(d2_step(&r, at + 400, &no_tag, &no_tag, 1) == D2_NONE);
        CHECK(d2_step(&r, at + 699, &no_tag, &no_tag, 1) == D2_NONE);
        CHECK(d2_step(&r, at + 700, &no_tag, &no_tag, 1) == D2_READY);
    }
    d2_init(&r, timing);
    CHECK(d2_step(&r, UINT32_MAX - 10u, &no_tag, &hf, 1) == D2_HF_FOUND);
    CHECK(d2_step(&r, 1988u, &no_tag, &no_tag, 1) == D2_NONE);
    CHECK(d2_step(&r, 1989u, &no_tag, &no_tag, 1) == D2_SINGLE_READY);
    {
        D2Timing bad = {0, 2000, 30000, 200};
        d2_init(&r, bad); CHECK(r.stage == D2_LOCKED);
        bad.removal_ms = 300; bad.pair_timeout_ms = 0;
        d2_init(&r, bad); CHECK(r.stage == D2_LOCKED);
        bad.pair_timeout_ms = 30000; bad.handoff_ms = 0x80000000u;
        d2_init(&r, bad); CHECK(r.stage == D2_LOCKED);
    }
}

int main(void)
{
    const uint8_t em[] = {1, 2, 3, 4, 5};
    const uint8_t mf[] = {0x11, 0x22, 0x33, 0x44};
    lf = uid(em, 40, "0102030405", 0x40);
    hf = uid(mf, 32, "11223344", 0x80);
    test_format();
    test_decimal_and_mixed_formats();
    test_single_presentation_and_host_handoff();
    test_single_cards_and_invalid();
    test_repeat_and_wrapping();
    printf("PASS: %u checks, one/two technology classification before output, single presentation, COM handoff, wrapping\n", checks);
    return 0;
}
