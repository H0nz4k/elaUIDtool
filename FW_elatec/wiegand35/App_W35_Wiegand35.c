// ******************************************************************
//  App_W35_Wiegand35.c
//
//  Produkční User App pro TWN4:
//    MIFARE UID → reverse bytes → 24 bitů → facility×100000+card
//    výstup: 8 číslic FFFCCCCC + CR
//
//  Ověřené páry:
//    AE1C56CF → 08607342
//    E9B20DFF → 01345801
//
//  Host kanál se volí při sestavení:
//    -DW35_HOST_CHANNEL=CHANNEL_USB   (USB CDC)
//    -DW35_HOST_CHANNEL=CHANNEL_COM1  (UART onboard)
// ******************************************************************

#include "twn4.sys.h"
#include "apptools.h"

#ifndef W35_HOST_CHANNEL
  #define W35_HOST_CHANNEL CHANNEL_USB
#endif

#ifndef CARDTIMEOUT
  #define CARDTIMEOUT 2000UL
#endif

#define MAXCARDSTRINGLEN 32

// Hledáme MIFARE (HF). LF necháváme vypnuté – Wiegand 3+5 ověřen na HF UID.
#define LFTAGTYPES  (NOTAG)
#define HFTAGTYPES  (TAGMASK(HFTAG_MIFARE))

// ******************************************************************
// ****** Wiegand 3+5 encoder ***************************************
// ******************************************************************

static bool EncodeWiegand35(const byte *ID, int IDBitCnt, char *Out, int MaxOutLen)
{
    byte raw[8];
    byte rev[8];
    byte window[4];
    int bytes;
    unsigned int value24;
    unsigned int facility;
    unsigned int card;
    unsigned int code;
    int i;

    if (IDBitCnt < 24 || MaxOutLen < 9)
        return false;

    // Pracujeme po bajtech – UID MIFARE Classic je typicky 32 bitů (4 B).
    bytes = (IDBitCnt + 7) / 8;
    if (bytes > (int)sizeof(raw))
        bytes = (int)sizeof(raw);

    for (i = 0; i < bytes; i++)
        raw[i] = ID[i];

    // Reverse byte order
    for (i = 0; i < bytes; i++)
        rev[i] = raw[bytes - 1 - i];

    // Drop first byte after reverse (= First Bit 8, Number of Bits 24)
    if (bytes < 4)
        return false;
    window[0] = rev[1];
    window[1] = rev[2];
    window[2] = rev[3];
    window[3] = 0;

    value24 = ((unsigned int)window[0] << 16)
            | ((unsigned int)window[1] << 8)
            | ((unsigned int)window[2]);

    facility = (value24 >> 16) & 0xFFu;
    card = value24 & 0xFFFFu;
    code = facility * 100000u + card;

    // Přesně 8 číslic s vedoucími nulami
    sprintf(Out, "%08u", code);
    return true;
}

bool ReadCardData(int TagType, const byte *ID, int IDBitCnt, char *CardString, int MaxCardStringLen)
{
    (void)TagType;
    CardString[0] = 0;
    return EncodeWiegand35(ID, IDBitCnt, CardString, MaxCardStringLen);
}

// ******************************************************************
// ****** Events ****************************************************
// ******************************************************************

void OnStartup(void)
{
    LEDInit(REDLED | GREENLED);
    LEDOn(GREENLED);
    LEDOff(REDLED);

    SetVolume(30);
    BeepLow();
    BeepHigh();

#if W35_HOST_CHANNEL == CHANNEL_COM1
    {
        TCOMParameters COMParameters;
        COMParameters.BaudRate = 9600;
        COMParameters.WordLength = COM_WORDLENGTH_8;
        COMParameters.Parity = COM_PARITY_NONE;
        COMParameters.StopBits = COM_STOPBITS_1;
        COMParameters.FlowControl = COM_FLOWCONTROL_NONE;
        SetCOMParameters(CHANNEL_COM1, &COMParameters);
    }
#endif

    SetHostChannel(W35_HOST_CHANNEL);
    SetTagTypes(LFTAGTYPES, HFTAGTYPES);
}

void OnNewCardFound(const char *CardString)
{
    HostWriteString(CardString);
    HostWriteString("\r");

    LEDOff(GREENLED);
    LEDOn(REDLED);
    LEDBlink(REDLED, 500, 500);

    SetVolume(100);
    BeepHigh();
}

void OnCardTimeout(const char *CardString)
{
    (void)CardString;
    LEDOn(GREENLED);
    LEDOff(REDLED);
}

void OnCardDone(void)
{
}

// ******************************************************************
// ****** Main ******************************************************
// ******************************************************************

int main(void)
{
    char OldCardString[MAXCARDSTRINGLEN + 1];

    OnStartup();
    OldCardString[0] = 0;

    while (true)
    {
        int TagType;
        int IDBitCnt;
        byte ID[32];

        if (SearchTag(&TagType, &IDBitCnt, ID, sizeof(ID)))
        {
            char NewCardString[MAXCARDSTRINGLEN + 1];
            if (ReadCardData(TagType, ID, IDBitCnt, NewCardString, sizeof(NewCardString) - 1))
            {
                if (strcmp(NewCardString, OldCardString) != 0)
                {
                    strcpy(OldCardString, NewCardString);
                    OnNewCardFound(NewCardString);
                }
                StartTimer(CARDTIMEOUT);
            }
            OnCardDone();
        }

        if (TestTimer())
        {
            OnCardTimeout(OldCardString);
            OldCardString[0] = 0;
        }
    }
}
