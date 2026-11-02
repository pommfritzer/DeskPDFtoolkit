#include <windows.h>
#include <shobjidl.h>
#include <shlwapi.h>
#include <shellapi.h>
#include <wrl.h>
#include <wrl/module.h>
#include <filesystem>
#include <string>

using Microsoft::WRL::ComPtr;
using Microsoft::WRL::Make;
using Microsoft::WRL::RuntimeClass;
using Microsoft::WRL::RuntimeClassFlags;
using Microsoft::WRL::ClassicCom;

static HMODULE module;

static std::wstring executable() {
    wchar_t path[32768];
    if (!GetModuleFileNameW(module, path, ARRAYSIZE(path))) return {};
    return (std::filesystem::path(path).parent_path().parent_path() / L"PDFtoolkit26.exe").wstring();
}

class __declspec(uuid("2A01975D-038C-43E2-A2D3-836ACF7A6803")) OpenCommand final
    : public RuntimeClass<RuntimeClassFlags<ClassicCom>, IExplorerCommand> {
public:
    IFACEMETHODIMP GetTitle(IShellItemArray*, PWSTR* title) override {
        return SHStrDupW(L"Open with PDFtoolkit26", title);
    }
    IFACEMETHODIMP GetIcon(IShellItemArray*, PWSTR* icon) override {
        return SHStrDupW((L"\"" + executable() + L"\",0").c_str(), icon);
    }
    IFACEMETHODIMP GetToolTip(IShellItemArray*, PWSTR* text) override {
        *text = nullptr;
        return E_NOTIMPL;
    }
    IFACEMETHODIMP GetCanonicalName(GUID* guid) override {
        *guid = __uuidof(OpenCommand);
        return S_OK;
    }
    IFACEMETHODIMP GetState(IShellItemArray* items, BOOL, EXPCMDSTATE* state) override {
        *state = ECS_HIDDEN;
        if (!items) return S_OK;
        DWORD count = 0;
        if (FAILED(items->GetCount(&count)) || !count) return S_OK;
        for (DWORD index = 0; index < count; ++index) {
            ComPtr<IShellItem> item;
            PWSTR path = nullptr;
            if (FAILED(items->GetItemAt(index, &item)) || FAILED(item->GetDisplayName(SIGDN_FILESYSPATH, &path))) return S_OK;
            bool pdf = _wcsicmp(PathFindExtensionW(path), L".pdf") == 0;
            CoTaskMemFree(path);
            if (!pdf) return S_OK;
        }
        *state = ECS_ENABLED;
        return S_OK;
    }
    IFACEMETHODIMP Invoke(IShellItemArray* items, IBindCtx*) override {
        EXPCMDSTATE state;
        GetState(items, FALSE, &state);
        if (state != ECS_ENABLED) return E_INVALIDARG;
        DWORD count = 0;
        items->GetCount(&count);
        std::wstring arguments = L"--shell-open";
        const auto exe = executable();
        auto launch = [&]() -> HRESULT {
            SHELLEXECUTEINFOW info = {sizeof(info)};
            info.fMask = SEE_MASK_FLAG_NO_UI;
            info.lpFile = exe.c_str();
            info.lpParameters = arguments.c_str();
            info.nShow = SW_SHOWNORMAL;
            return ShellExecuteExW(&info) ? S_OK : HRESULT_FROM_WIN32(GetLastError());
        };
        for (DWORD index = 0; index < count; ++index) {
            ComPtr<IShellItem> item;
            PWSTR path = nullptr;
            HRESULT hr = items->GetItemAt(index, &item);
            if (FAILED(hr)) return hr;
            hr = item->GetDisplayName(SIGDN_FILESYSPATH, &path);
            if (FAILED(hr)) return hr;
            std::wstring argument = L" \"" + std::wstring(path) + L"\"";
            CoTaskMemFree(path);
            if (arguments.size() + argument.size() > 28000) {
                hr = launch();
                if (FAILED(hr)) return hr;
                arguments = L"--shell-open";
            }
            arguments += argument;
        }
        return launch();
    }
    IFACEMETHODIMP GetFlags(EXPCMDFLAGS* flags) override { *flags = ECF_DEFAULT; return S_OK; }
    IFACEMETHODIMP EnumSubCommands(IEnumExplorerCommand** commands) override { *commands = nullptr; return E_NOTIMPL; }
};

class Factory final : public RuntimeClass<RuntimeClassFlags<ClassicCom>, IClassFactory> {
public:
    IFACEMETHODIMP CreateInstance(IUnknown* outer, REFIID iid, void** object) override {
        if (outer) return CLASS_E_NOAGGREGATION;
        return Make<OpenCommand>().CopyTo(iid, object);
    }
    IFACEMETHODIMP LockServer(BOOL) override { return S_OK; }
};

STDAPI DllGetClassObject(REFCLSID clsid, REFIID iid, void** object) {
    Microsoft::WRL::Module<Microsoft::WRL::InProc>::GetModule();
    if (clsid != __uuidof(OpenCommand)) return CLASS_E_CLASSNOTAVAILABLE;
    return Make<Factory>().CopyTo(iid, object);
}
STDAPI DllCanUnloadNow() { return Microsoft::WRL::Module<Microsoft::WRL::InProc>::GetModule().GetObjectCount() == 0 ? S_OK : S_FALSE; }
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) { module = instance; DisableThreadLibraryCalls(instance); }
    return TRUE;
}
