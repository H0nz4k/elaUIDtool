#ifndef D2_REGISTRATION_SIGNAL_H
#define D2_REGISTRATION_SIGNAL_H
#include "dual_core.h"
void d2_signal_init(void);
void d2_signal_action(const D2Reader *reader, D2Action action);
#endif
