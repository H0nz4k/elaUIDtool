// *******************************************************************
// **                                                               **
// ** File: appconfig.h                                             **
// ** Date: 29.04.2024                                              **
// ** Time: 21:38                                                   **
// **                                                               **
// ** This file was generated as part of a project by:              **
// ** AppBlaster V4.80                                              **
// **                                                               **
// *******************************************************************

#ifndef __APPCONFIG_H__
#define __APPCONFIG_H__

#define LFTAGTYPES              (NOTAG)
#define HFTAGTYPES              (TAGMASK(HFTAG_HIDICLASS))
#define CARDTIMEOUT             2000UL      // Timeout in milliseconds
#define MAXCARDIDLEN            32          // Length in bytes
#define MAXCARDSTRINGLEN        256         // Length W/O null-termination
#define CONFIGENABLED           SUPPORT_UPGRADECARD_ON
#define SEARCH_BLE(a,b,c,d)     false
#define BLE_MASK                0

bool ReadCardData(int TagType,const byte *ID,int IDBitCnt,char *CardString,int MaxCardStringLen);
void OnStartup(void);
void OnNewCardFound(const char *CardString);
void OnCardTimeout(const char *CardString);
void OnCardFound(const char *CardString);
void OnCardDone(void);

#endif
