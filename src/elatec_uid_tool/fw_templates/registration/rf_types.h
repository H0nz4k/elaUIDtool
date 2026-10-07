#ifndef D2_RF_TYPES_H
#define D2_RF_TYPES_H

/* Called with GetSupportedTagTypes, so unavailable/licensed-out types are
 * never enabled. LF includes the SDK's 125/134.2 kHz group. HF is 13.56 MHz
 * physical card/tag technologies, excluding BLE and NFC peer-to-peer. */
static inline unsigned int d2_hf_card_types(unsigned int supported)
{
    return supported & ~(TAGMASK(HFTAG_BLE) | TAGMASK(HFTAG_BLELC) |
                         TAGMASK(HFTAG_NFCP2P));
}

static inline int d2_type_in_band(int type, unsigned int enabled, int hf)
{
    int first = hf ? 0x80 : 0x40;
    return type >= first && type < first + 32 &&
           (enabled & TAGMASK(type)) != 0;
}

#endif
