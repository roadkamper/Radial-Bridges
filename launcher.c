#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
#include <stdlib.h>

typedef int (__cdecl *PyMainFunction)(int,wchar_t **);
typedef HRESULT (WINAPI *SetAppUserModelIdFunction)(PCWSTR);

int WINAPI wWinMain(HINSTANCE h,HINSTANCE prev,LPWSTR args,int show){
    wchar_t exe[32768],root[32768],python[32768],dll[32768],script[32768];
    DWORD n=GetModuleFileNameW(NULL,exe,32768);
    if(!n||n>=32768)return 1;
    wcscpy(root,exe);wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 1;*slash=0;
    if(wcslen(root)>32000)return 1;
    swprintf(python,32768,L"%ls\\runtime\\python.exe",root);
    swprintf(dll,32768,L"%ls\\runtime\\python312.dll",root);
    swprintf(script,32768,L"%ls\\app.py",root);
    if(GetFileAttributesW(python)==INVALID_FILE_ATTRIBUTES||GetFileAttributesW(dll)==INVALID_FILE_ATTRIBUTES||GetFileAttributesW(script)==INVALID_FILE_ATTRIBUTES){
        MessageBoxW(NULL,L"The bundled runtime is missing. Reinstall Radial Bridges using its setup executable.",L"Radial Bridges",MB_OK|MB_ICONERROR);return 1;
    }
    HMODULE shell=GetModuleHandleW(L"shell32.dll");
    SetAppUserModelIdFunction setAppId=shell?(SetAppUserModelIdFunction)GetProcAddress(shell,"SetCurrentProcessExplicitAppUserModelID"):NULL;
    if(setAppId)setAppId(L"OolieIndustries.RadialBridges");
    HMODULE runtime=LoadLibraryExW(dll,NULL,LOAD_WITH_ALTERED_SEARCH_PATH);
    if(!runtime){MessageBoxW(NULL,L"Unable to load the bundled Python runtime. Reinstall Radial Bridges.",L"Radial Bridges",MB_OK|MB_ICONERROR);return 1;}
    PyMainFunction pyMain=(PyMainFunction)GetProcAddress(runtime,"Py_Main");
    if(!pyMain){MessageBoxW(NULL,L"The bundled Python runtime is incompatible. Reinstall Radial Bridges.",L"Radial Bridges",MB_OK|MB_ICONERROR);FreeLibrary(runtime);return 1;}
    int originalCount=0;
    wchar_t **original=CommandLineToArgvW(GetCommandLineW(),&originalCount);
    if(!original||originalCount<1){FreeLibrary(runtime);return 1;}
    int pythonCount=originalCount+1;
    wchar_t **pythonArgs=calloc((size_t)pythonCount+1,sizeof(wchar_t *));
    if(!pythonArgs){LocalFree(original);FreeLibrary(runtime);return 1;}
    pythonArgs[0]=python;pythonArgs[1]=script;
    for(int i=1;i<originalCount;i++)pythonArgs[i+1]=original[i];
    SetCurrentDirectoryW(root);
    int code=pyMain(pythonCount,pythonArgs);
    free(pythonArgs);LocalFree(original);FreeLibrary(runtime);return code;
}
