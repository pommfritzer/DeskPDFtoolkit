#include <windows.h>
#include <shobjidl.h>
#include <wrl.h>
#include <iostream>

int wmain(int argc, wchar_t** argv) {
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    CLSID clsid;
    CLSIDFromString(L"{2A01975D-038C-43E2-A2D3-836ACF7A6803}", &clsid);
    Microsoft::WRL::ComPtr<IExplorerCommand> command;
    HRESULT hr = CoCreateInstance(clsid, nullptr, CLSCTX_LOCAL_SERVER, IID_PPV_ARGS(&command));
    if (FAILED(hr)) { std::wcerr << L"Activation failed: " << std::hex << hr; return 1; }
    PWSTR title = nullptr, icon = nullptr;
    command->GetTitle(nullptr, &title);
    command->GetIcon(nullptr, &icon);
    std::wcout << title << L"\n" << icon << L"\n";
    bool valid = title && wcscmp(title, L"Open with PDFtoolkit26") == 0;
    CoTaskMemFree(title);
    CoTaskMemFree(icon);
    if (!valid) return 2;
    if (argc > 1) {
        Microsoft::WRL::ComPtr<IShellItem> item;
        Microsoft::WRL::ComPtr<IShellItemArray> items;
        hr = SHCreateItemFromParsingName(argv[1], nullptr, IID_PPV_ARGS(&item));
        if (FAILED(hr)) return 3;
        SHCreateShellItemArrayFromShellItem(item.Get(), IID_PPV_ARGS(&items));
        EXPCMDSTATE state;
        command->GetState(items.Get(), FALSE, &state);
        std::wcout << L"PDF state: " << state << L"\n";
        if (state != ECS_ENABLED) return 4;
        hr = command->Invoke(items.Get(), nullptr);
        if (FAILED(hr)) { std::wcerr << std::hex << hr; return 5; }
    }
    return 0;
}
