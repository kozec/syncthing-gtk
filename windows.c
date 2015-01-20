/**
 * Syncthing-GTK - Windows related stuff, C part.
 * Windows only code compiled to dll and loaded by syncthing_gtk.windows
 * 
 * Compile using:
 * $ gcc -I/c/Python27/include/ -c windows.c
 * $ gcc -L/c/Python27/libs/ -shared -o st-gtk-windows.dll windows.o -lpython27
 *
 * $ gcc -c windows.c && gcc -shared -o st-gtk-windows.dll windows.o
 */

#include <windows.h>
#include <stdio.h>
#include <Windowsx.h>

typedef int bool;
typedef struct _CORNERS {
  int left;
  int right;
  int top;
  int bottom;
} CORNERS;
typedef int (*themeChangedCallbackType) ();

CORNERS windowCorners;
bool hitTestEnabled = FALSE;
themeChangedCallbackType themeChangedCallback = NULL;

WNDPROC original_wndproc;

/** Hit test the frame for resizing and moving
 * http://msdn.microsoft.com/en-us/library/windows/desktop/bb688195(v=vs.85).aspx#appendixc
 */
LRESULT HitTestNCA(HWND hWnd, WPARAM wParam, LPARAM lParam) {
	// Get the point coordinates for the hit test.
	POINT ptMouse = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};

	// Get the window rectangle.
	RECT rcWindow;
	GetWindowRect(hWnd, &rcWindow);

	// Get the frame rectangle, adjusted for the style without a caption.
	RECT rcFrame = { 0 };
	AdjustWindowRectEx(&rcFrame, WS_OVERLAPPEDWINDOW & ~WS_CAPTION, FALSE, 0);

	// Determine if the hit test is for resizing. Default middle (1,1).
	USHORT uRow = 1;
	USHORT uCol = 1;
	bool fOnResizeBorder = FALSE;

	// Determine if the point is at the top or bottom of the window.
	if (ptMouse.y >= rcWindow.top && ptMouse.y < rcWindow.top + windowCorners.top) {
		fOnResizeBorder = (ptMouse.y < (rcWindow.top - rcFrame.top));
		uRow = 0;
	} else if (ptMouse.y < rcWindow.bottom && ptMouse.y >= rcWindow.bottom - windowCorners.bottom) {
		uRow = 2;
	}

	// Determine if the point is at the left or right of the window.
	if (ptMouse.x >= rcWindow.left && ptMouse.x < rcWindow.left + windowCorners.left) {
		uCol = 0; // left side
	} else if (ptMouse.x < rcWindow.right && ptMouse.x >= rcWindow.right - windowCorners.right) {
		uCol = 2; // right side
	}

	// Hit test (HTTOPLEFT, ... HTBOTTOMRIGHT)
	LRESULT hitTests[3][3] = {
		{ HTTOPLEFT,    fOnResizeBorder ? HTTOP : HTCAPTION,    HTTOPRIGHT },
		{ HTLEFT,       HTNOWHERE,     HTRIGHT },
		{ HTBOTTOMLEFT, HTBOTTOM, HTBOTTOMRIGHT },
	};

	return hitTests[uRow][uCol];
}


/** Window message handler installed by handle_wm_nccalcsize */
LRESULT CALLBACK _wm_nccalcsize_handler(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
	LRESULT rv;
	if ((uMsg == WM_NCCALCSIZE) && (wParam == TRUE)) {
		NCCALCSIZE_PARAMS* params = (NCCALCSIZE_PARAMS*)lParam;
		params->rgrc[0].left   = params->rgrc[0].left   + 0;
		params->rgrc[0].top    = params->rgrc[0].top    + 0;
		params->rgrc[0].right  = params->rgrc[0].right  - 0;
		params->rgrc[0].bottom = params->rgrc[0].bottom - 0;
		return 0;
	}
	else if (uMsg == WM_SYSCOLORCHANGE) {
		if (themeChangedCallback != NULL) 
			themeChangedCallback();
	}
	else if (hitTestEnabled && (uMsg == WM_NCHITTEST)) {
		rv = HitTestNCA(hwnd, wParam, lParam);
		if (rv != HTNOWHERE)
			return rv;
	}
	return CallWindowProc(original_wndproc, hwnd, uMsg, wParam, lParam);
}

/**
 * Sets handler (callable python object) for WM_THEMECHANGED message.
 * Reference to this object will be held until program ends or other
 * handler is set.
 * Returns 0 on success;
 */
int on_wm_themechanged(themeChangedCallbackType callback) {
	themeChangedCallback = callback;
	return 0;
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

/**
 * Adds resizing to already installed custom message handler.
 * Returns 0 on success, what's always.
 */
int make_resizable(CORNERS* corners) {
	windowCorners = *corners;
	hitTestEnabled = TRUE;
	return 0;
}
