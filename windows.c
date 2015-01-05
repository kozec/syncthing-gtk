/**
 * Syncthing-GTK - Windows related stuff, C part.
 * Windows only code compiled to dll and loaded by syncthing_gtk.windows
 * 
 * Compile using:
 * $ gcc -c windows.c && gcc -shared -o st-gtk-windows.dll windows.o
 */

#include <windows.h>
#include <stdio.h>

WNDPROC original_wndproc;

/** Window message handler installed by handle_wm_nccalcsize */
LRESULT CALLBACK _wm_nccalcsize_handler(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
	if (uMsg == WM_NCCALCSIZE) {
		if (wParam == TRUE) {
			NCCALCSIZE_PARAMS* params = (NCCALCSIZE_PARAMS*)lParam;
			printf ("HANDLED: WM_NCCALCSIZE\n");
			params->rgrc[0].left   = params->rgrc[0].left   + 0;
			params->rgrc[0].top    = params->rgrc[0].top    + 0;
			params->rgrc[0].right  = params->rgrc[0].right  - 0;
			params->rgrc[0].bottom = params->rgrc[0].bottom - 0;
			return 0;
		}
	}
	LRESULT rv = CallWindowProc(original_wndproc, hwnd, uMsg, wParam, lParam);
	return rv;
}

/** 
 * Install custom window message handler for WM_NCCALCSIZE message.
 * Handling this message allows GTK to use entire window area, including
 * area normaly reserved for title and icon, for drawing.
 */
int handle_wm_nccalcsize(HWND hWnd) {
  original_wndproc = (WNDPROC)SetWindowLongW(hWnd, GWL_WNDPROC, (long)_wm_nccalcsize_handler);
  if (original_wndproc == 0) {
	  fprintf (stderr, "handle_wm_nccalcsize: Failed to install wm_nccalcsize handler. Error %lu\n", GetLastError());
	  return 1;
  }
  printf ("wm_nccalcsize handler installed.\n");
  return 0;
}
