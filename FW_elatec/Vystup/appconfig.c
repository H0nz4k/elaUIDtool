// *******************************************************************
// **                                                               **
// ** File: appconfig.c                                             **
// ** Date: 29.04.2024                                              **
// ** Time: 21:38                                                   **
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

bool ReadType1(int TagType,const byte *ID,int IDBitCnt,char *CardString,int MaxCardStringLen)
{
    // ------ STEP 1: Test and read data from transponder ------------
    if (TagType != HFTAG_HIDICLASS)
        return false;
    byte CardData[256];
    int CardDataBitCnt;
    byte PACBits[32];
    int PACBitCnt;
    if (!ICLASS_GetPACBits(PACBits,&PACBitCnt,sizeof(PACBits)))
        return false;
    if (PACBitCnt != 26)
        return false;
    CardDataBitCnt = MIN(PACBitCnt,sizeof(CardData)*8);
    CopyBits(CardData,0,PACBits,0,CardDataBitCnt);

    // ------ STEP 2: Do bit manipulation ----------------------------

    // (No bit manipulation specified)

    // ------ STEP 3: Format output data -----------------------------
    int RemainingDigits, MinFieldDigits, MaxFieldDigits, FieldBitCnt;
    char *WritePos = CardString;
    *WritePos = 0;
    // ------ Field 1 (Decimal) --------------------------------------
    const char *Prefix1 = ",";
    RemainingDigits = MaxCardStringLen - strlen(CardString);
    MaxFieldDigits = MIN(RemainingDigits,strlen(Prefix1));
    strncpy(WritePos,Prefix1,MaxFieldDigits);
    WritePos += MaxFieldDigits;
    *WritePos = 0;
    RemainingDigits = MaxCardStringLen - strlen(CardString);
    // Output all digits of the field
     MaxFieldDigits = MIN(RemainingDigits, 5);
    MinFieldDigits = MIN(MaxFieldDigits, 5);
    FieldBitCnt = 8;
    // Convert data to ASCII using radix 10
    WritePos += ConvertBinaryToString(CardData, 10, FieldBitCnt, WritePos, 10, MinFieldDigits, MaxFieldDigits);
    // ------ Field 2 (Decimal) --------------------------------------
    RemainingDigits = MaxCardStringLen - strlen(CardString);
    // Length of output is exactly 5 digits
     MaxFieldDigits = MIN(RemainingDigits, 5);
    MinFieldDigits = MIN(MaxFieldDigits, 5);
    FieldBitCnt = 16;
    // Convert data to ASCII using radix 10
    WritePos += ConvertBinaryToString(CardData, 9, FieldBitCnt, WritePos, 10, MinFieldDigits, MaxFieldDigits);
    // ------ Field 3 (Hexadecimal) ----------------------------------
    const char *Prefix3 = ",";
    RemainingDigits = MaxCardStringLen - strlen(CardString);
    MaxFieldDigits = MIN(RemainingDigits,strlen(Prefix3));
    strncpy(WritePos,Prefix3,MaxFieldDigits);
    WritePos += MaxFieldDigits;
    *WritePos = 0;
    RemainingDigits = MaxCardStringLen - strlen(CardString);
    // Output all digits of the field
     MaxFieldDigits = MIN(RemainingDigits, 3);
    MinFieldDigits = MIN(MaxFieldDigits, 3);
    FieldBitCnt = 8;
    // By default, the number of digits of a hexadecimal number is a multiple of two
    MinFieldDigits = MAX((FieldBitCnt + 7) / 8 * 2, MinFieldDigits);
    // Convert data to ASCII using radix 16
    WritePos += ConvertBinaryToString(CardData, 10, FieldBitCnt, WritePos, 16, MinFieldDigits, MaxFieldDigits);
    // ------ Field 4 (Hexadecimal) ----------------------------------
    RemainingDigits = MaxCardStringLen - strlen(CardString);
    // Length of output is exactly 5 digits
    MaxFieldDigits = MIN(RemainingDigits, 5);
    MinFieldDigits = MIN(MaxFieldDigits, 5);
    FieldBitCnt = 16;
    // Convert data to ASCII using radix 16
    WritePos += ConvertBinaryToString(CardData, 9, FieldBitCnt, WritePos, 16, MinFieldDigits, MaxFieldDigits);
    // ---------------------------------------------------------------

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
    SetHostChannel(CHANNEL_COM1);
}

// take a hex string and convert it to a 32bit number (max 8 hex digits)
unsigned int hex2int(char *hex, char *end) {
    unsigned int val = 0;
    while (hex != end) {
        // get current character then increment
        char byte = *hex++; 
        // transform hex character to the 4bit equivalent number, using the ascii table indexes
        if (byte >= '0' && byte <= '9') byte = byte - '0';
        else if (byte >= 'a' && byte <='f') byte = byte - 'a' + 10;
        else if (byte >= 'A' && byte <='F') byte = byte - 'A' + 10;    
        // shift 4 to make space for new digit, and add the 4 bits of the new digit 
        val = (val << 4) | (byte & 0xF);
    }
    return val;
}

#define DEC_DIGITS 10

// Function to convert a given decimal number
// to a base 'base' and
char* fromDeci(char *res, unsigned int inputNum)
{
    int index = 0; // Initialize index of result
 
    // Convert input number is given base by repeatedly
    // dividing it by base and taking remainder
    while (index < DEC_DIGITS) // fixed number of output chars
    {
        res[index++] = (char)((inputNum % 10) + '0');
        inputNum /= 10;
    }
 
    return res;
}

#ifndef MAXCARDSTRINGLEN
// standalone debug
#include <string.h>
#define MAXCARDSTRINGLEN		128   	// Length W/O null-termination
#endif

void OnNewCardFound(const char *OldCardString)
{
    char CardString[MAXCARDSTRINGLEN+1]; // copy so we can change it
    strcpy(CardString,OldCardString);

    const int decOffset = 1; // card string starts with ","

    unsigned int cardid = hex2int(CardString + decOffset+10+1, CardString + decOffset+10+1+8);
    char res[DEC_DIGITS];
    fromDeci(res, cardid);
    // res now contains reversed dec string
    
    int index = 0;
    while (index < DEC_DIGITS)
    {
        CardString[decOffset+index] = res[DEC_DIGITS-index-1];
        ++index;
    }
    HostWriteString(">20");
    HostWriteString(CardString);
    HostWriteString("\n");
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
