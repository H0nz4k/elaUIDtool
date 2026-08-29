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

    // Vytažení FC (8 bitů) a ID (16 bitů)
    unsigned int FC = 0;
    unsigned int IDval = 0;

    // FC je od bitu 1 do 8 (index 1–8), protože bit 0 je parita
    for (int i = 1; i <= 8; i++) {
        int byteIndex = i / 8;
        int bitIndex = 7 - (i % 8);
        int bit = (PACBits[byteIndex] >> bitIndex) & 1;
        FC = (FC << 1) | bit;
    }

    // ID je od bitu 9 do 24
    for (int i = 9; i <= 24; i++) {
        int byteIndex = i / 8;
        int bitIndex = 7 - (i % 8);
        int bit = (PACBits[byteIndex] >> bitIndex) & 1;
        IDval = (IDval << 1) | bit;
    }

    snprintf(CardString, MaxCardStringLen, "%03u%05u", FC, IDval);
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
    HostWriteString(">20");
    HostWriteString(CardString);
    HostWriteString("\r");
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
