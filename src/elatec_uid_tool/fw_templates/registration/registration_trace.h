#ifndef D2_REGISTRATION_TRACE_H
#define D2_REGISTRATION_TRACE_H
#include "dual_core.h"
void d2_trace_pair(const D2Reader *reader);
void d2_trace_init(unsigned int lf, unsigned int hf);
void d2_trace_poll(D2Reader *reader);
int d2_host_ready(void);
void d2_trace_band(char band);
void d2_trace_read(char band, int type, int bits, int found, int rf,
                   unsigned int error, unsigned int search_ms, const D2Uid *uid);
void d2_trace_action(D2Reader *reader, D2Stage before, D2Action action);
void d2_trace_heartbeat(D2Reader *reader, uint32_t now);
#endif
