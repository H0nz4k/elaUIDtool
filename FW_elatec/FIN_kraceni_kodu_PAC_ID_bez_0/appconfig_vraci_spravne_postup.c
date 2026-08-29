// *******************************************************************
// **                                                               **
// ** File: appconfig.c                                             **
// ** Date: 15.05.2024                                              **
// ** Time: 11:47                                                   **
// **                                                               **
// ** This file was generated as part of a project by:              **
// ** AppBlaster V4.80                                              **
// **                                                               **
// *******************************************************************

#include "twn4.sys.h"
#include "apptools.h"
#include "appconfig.h"

// *******************************************************************
// ****** Global Variables *******************************************
// *******************************************************************

// ------ Options --------------------------------

const byte AppManifest[] =
{
    USB_KEYBOARDREPEATRATE, 1, 10,
    USB_KEYBOARDLAYOUT, 1, USB_KEYBOARDLAYOUT_ENGLISH,
    USB_KEYBOARDSENDALTCODES, 1, USB_KEYBOARDSENDALTCODES_OFF,
    USB_SERIALNUMBER, 1, USB_SERIALNUMBER_OFF,
    USB_SUPPORTREMOTEWAKEUP, 1, USB_SUPPORTREMOTEWAKEUP_OFF,
    EXECUTE_APP, 1, EXECUTE_APP_AUTO,
    ENABLE_WATCHDOG, 1, WATCHDOG_ON,
    TLV_END
};

// ------ Transponder-Specific Variables ---------

// *******************************************************************
// ****** HID iCLASS/SEOS (PAC, 26 bits) *****************************
// *******************************************************************
int GetBit(const byte *bits, int bitIndex) {
    int byteIndex = bitIndex / 8;
    int bitInByte = 7 - (bitIndex % 8); // MSB first
    return (bits[byteIndex] >> bitInByte) & 1;
}


bool ReadType1(int TagType, const byte *ID, int IDBitCnt, char *CardString, int MaxCardStringLen)
{
    if (TagType != HFTAG_HIDICLASS)
        return false;

    byte PACBits[32];
    int PACBitCnt;

    if (!ICLASS_GetPACBits(PACBits, &PACBitCnt, sizeof(PACBits)))
        return false;

    if (PACBitCnt < 26)
        return false;

    // Facility Code = bity 1 až 8 (indexy 1–8)
    unsigned int FC = 0;
    for (int i = 1; i <= 8; i++) {
        FC = (FC << 1) | GetBit(PACBits, i);
    }

    // ID = bity 9 až 24
    unsigned int IDval = 0;
    for (int i = 9; i <= 24; i++) {
        IDval = (IDval << 1) | GetBit(PACBits, i);
    }

    // Sestavení finálního čísla
    unsigned int FullCode = FC * 100000 + IDval;

    snprintf(CardString, MaxCardStringLen, "%u", FullCode);
    return true;
}


// *******************************************************************
// ****** Transponder Evaluation Function ****************************
// *******************************************************************

bool ReadCardData(int TagType,const byte *ID,int IDBitCnt,char *CardString,int MaxCardStringLen)
{
    if (ReadType1(TagType,ID,IDBitCnt,CardString,MaxCardStringLen))
        return true;
    return false;
}

// *******************************************************************
// ****** Event Handler **********************************************
// *******************************************************************

void OnStartup(void)
{
    CompLEDInit(REDLED | YELLOWLED | GREENLED);
    CompLEDOff(REDLED);
    CompLEDOff(YELLOWLED);
    CompLEDOn(GREENLED);
    SetVolume(30);
    BeepLow();
    BeepHigh();
    SetTagTypes(LFTAGTYPES, HFTAGTYPES);
}

void OnNewCardFound(const char *CardString)
{
    HostWriteString(">20,");
    
    // Přeskočíme počáteční nuly, ale necháme alespoň jednu číslici
    const char *p = CardString;
    while (*p == '0' && *(p + 1) != '\0') {
        p++;
    }

    HostWriteString(p);
    HostWriteString("\n");
    CompLEDOn(REDLED);
    CompLEDBlink(REDLED,500,500);
    CompLEDOff(YELLOWLED);
    CompLEDOff(GREENLED);
    SetVolume(100);
    BeepHigh();
}

void OnCardTimeout(const char *CardString)
{
    CompLEDOff(REDLED);
    CompLEDOff(YELLOWLED);
    CompLEDOn(GREENLED);
}

void OnCardFound(const char *CardString)
{
}

void OnCardDone(void)
{
}
