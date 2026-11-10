#include "4DPlugin-JSON.h"
#include "C_TEXT.h"
#include "ARRAY_TEXT.h"
#include "PrivateTypes.h"
#include "EntryPoints.h"

#include <cassert>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>

namespace {
using Text = std::basic_string<PA_Unichar>;
std::map<PA_Unichar*, size_t> strings;
std::map<PA_Handle, size_t> handles;
struct Ref {
    size_t owners = 1;
    std::map<Text, PA_Variable> values;
};
std::map<void*, Ref*> refs;
bool nullEmpty = false;
bool failGet = false;
bool failSet = false;
bool failStringify = false;
bool mismatchStringify = false;
size_t failedGets = 0;
const PA_Unichar empty[] = {0};
const PA_Unichar ascii[] = {'A', 'l', 'i', 'a', 's', 0};
const PA_Unichar bmp[] = {0x65e5, 0x672c, 0};
const PA_Unichar supplementary[] = {'A', 0xd83d, 0xde00, 0};
const PA_Unichar* fixtures[] = {ascii, bmp, supplementary, empty};
const char* utf8[] = {"Alias", "\xe6\x97\xa5\xe6\x9c\xac", "A\xf0\x9f\x98\x80", ""};
const wchar_t* wide[] = {L"Alias", L"\u65e5\u672c", L"A\U0001f600", L""};

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << '\n';
        std::abort();
    }
}

Text text(const PA_Unichar* value) {
    return value ? Text(value) : Text();
}

PA_Unistring makeString(const PA_Unichar* value) {
    const Text copy = text(value);
    PA_Unistring result = {};
    result.fLength = static_cast<PA_long32>(copy.size());
    if (!copy.empty() || !nullEmpty) {
        result.fString = new PA_Unichar[copy.size() + 1];
        std::memcpy(result.fString, copy.c_str(), (copy.size() + 1) * sizeof(PA_Unichar));
        PA_Unichar* buffer = result.fString;
        strings[buffer] = copy.size();
    }
    return result;
}

Text readString(PA_Unistring value) {
    if (!value.fString) {
        require(value.fLength == 0, "null string with nonzero length");
        return Text();
    }
    PA_Unichar* buffer = value.fString;
    auto it = strings.find(buffer);
    require(it != strings.end(), "read of disposed/unowned string");
    require(it->second == static_cast<size_t>(value.fLength), "UTF-16 length mismatch");
    require(value.fString[value.fLength] == 0, "missing UTF-16 terminator");
    return Text(value.fString, value.fLength);
}

void freeString(PA_Unistring value) {
    if (value.fString) {
        PA_Unichar* buffer = value.fString;
        require(strings.erase(buffer) == 1, "double disposal or borrowed string disposal");
        delete[] value.fString;
    }
}

void* newRef() {
    Ref* ref = new Ref;
    refs[ref] = ref;
    return ref;
}

void retain(void* ref) {
    if (ref) {
        require(refs.count(ref), "retaining dead reference");
        ++refs.at(ref)->owners;
    }
}

void clear(PA_Variable& value);

void release(void* ref) {
    if (!ref) return;
    require(refs.count(ref), "releasing dead reference");
    Ref* object = refs.at(ref);
    if (--object->owners == 0) {
        for (auto& entry : object->values) clear(entry.second);
        refs.erase(ref);
        delete object;
    }
}

PA_Variable copyVariable(PA_Variable value) {
    if (value.fType == eVK_Unistring) {
        Text copy = readString(value.uValue.fString);
        value.uValue.fString = makeString(copy.c_str());
    } else if (value.fType == eVK_Object) {
        retain(value.uValue.fObject);
    } else if (value.fType == eVK_Collection) {
        retain(value.uValue.fCollection);
    }
    return value;
}

void clear(PA_Variable& value) {
    switch (value.fType) {
        case eVK_Unistring:
            freeString(value.uValue.fString);
            break;
        case eVK_Object:
            release(value.uValue.fObject);
            break;
        case eVK_Collection:
            release(value.uValue.fCollection);
            break;
        case eVK_ArrayUnicode: {
            PA_Handle handle = value.uValue.fArray.fData;
            require(handles.count(handle), "clearing dead array");
            auto data = reinterpret_cast<PA_Unistring*>(*handle);
            for (int i = 0; i <= value.uValue.fArray.fNbElements; ++i) freeString(data[i]);
            PA_DisposeHandle(handle);
            break;
        }
        case eVK_Undefined:
        case eVK_Null:
        case eVK_Real:
        case eVK_Longint:
        case eVK_Boolean:
            break;
        default:
            require(false, "unexpected variable cleanup (possibly failed getter output)");
    }
    value = {};
    value.fType = eVK_Undefined;
}

void balanced(const char* message) {
    require(strings.empty() && handles.empty() && refs.empty(), message);
}

void engine(short selector, EngineBlock* eb) {
    switch (selector) {
        case EX_CREATE_UNISTRING:
            eb->fUniString1 = makeString(reinterpret_cast<PA_Unichar*>(eb->fHandle));
            break;
        case EX_DISPOSE_UNISTRING:
            freeString(eb->fUniString1);
            break;
        case EX_SET_UNISTRING: {
            Text copy = text(reinterpret_cast<PA_Unichar*>(eb->fHandle));
            freeString(eb->fUniString1);
            eb->fUniString1 = makeString(copy.c_str());
            break;
        }
        case EX_VARIABLE_TO_STRING: {
            auto value = reinterpret_cast<PA_Variable*>(eb->fHandle);
            require(value->fType == eVK_Unistring, "string getter on wrong variable kind");
            readString(value->uValue.fString);
            eb->fUniString1 = value->uValue.fString;
            break;
        }
        case EX_CLEAR_VARIABLE:
            clear(*static_cast<PA_Variable*>(eb->fPtr1));
            break;
        case EX_HANDLE_MANAGER: {
            PA_Handle handle = eb->fHandle;
            switch (eb->fParam1) {
                case 1:
                    handle = new char*;
                    *handle = static_cast<char*>(std::calloc(1, std::max<sLONG_PTR>(1, static_cast<sLONG_PTR>(eb->fParam2))));
                    handles[handle] = eb->fParam2;
                    eb->fHandle = handle;
                    break;
                case 2:
                    require(handles.erase(handle) == 1, "double handle disposal");
                    std::free(*handle);
                    delete handle;
                    break;
                case 3:
                    require(handles.count(handle), "resize dead handle");
                    *handle = static_cast<char*>(std::realloc(*handle, std::max<sLONG_PTR>(1, static_cast<sLONG_PTR>(eb->fParam2))));
                    handles[handle] = eb->fParam2;
                    break;
                case 4:
                    eb->fParam2 = handles.at(handle);
                    break;
                case 5:
                    require(handles.count(handle), "lock dead handle");
                    eb->fParam3 = reinterpret_cast<sLONG_PTR>(*handle);
                    break;
                case 6:
                    require(handles.count(handle), "unlock dead handle");
                    break;
                default:
                    require(false, "unexpected handle operation");
            }
            break;
        }
        case EX_SET_OBJ_VALUE: {
            Text key = readString(eb->fUniString1);
            if (failSet) {
                eb->fError = eER_IncompatibleTypes;
                break;
            }
            Ref* object = refs.at(static_cast<void*>(eb->fPtr1));
            PA_Variable copy = copyVariable(*static_cast<PA_Variable*>(eb->fPtr2));
            auto found = object->values.find(key);
            if (found != object->values.end()) clear(found->second);
            object->values[key] = copy;
            break;
        }
        case EX_GET_OBJ_VALUE: {
            if (failGet) {
                ++failedGets;
                // SDK output is unspecified on error. Poison it, not a valid owner.
                std::memset(eb->fPtr2, 0xa5, sizeof(PA_Variable));
                eb->fError = eER_IncompatibleTypes;
                break;
            }
            Ref* object = refs.at(static_cast<void*>(eb->fPtr1));
            Text key = eb->fShort == eVK_Collection ? Text() : readString(eb->fUniString1);
            *static_cast<PA_Variable*>(eb->fPtr2) = copyVariable(object->values.at(key));
            break;
        }
        case EX_EXECUTE_COMMAND_BY_ID: {
            auto args = static_cast<PA_Variable**>(eb->fPtr1);
            auto result = static_cast<PA_Variable*>(eb->fPtr2);
            switch (eb->fParam1) {
                case 1231:
                    PA_SetBooleanVariable(result,
                        refs.at(static_cast<void*>(args[0]->uValue.fObject))->values.count(readString(args[1]->uValue.fString)) != 0);
                    break;
                case 1225: {
                    void* clone = newRef();
                    for (auto& entry : refs.at(static_cast<void*>(args[0]->uValue.fObject))->values)
                        refs.at(clone)->values[entry.first] = copyVariable(entry.second);
                    PA_SetObjectVariable(result, clone);
                    break;
                }
                case 1217:
                    if (failStringify) {
                        eb->fError = eER_IncompatibleTypes;
                    } else if (mismatchStringify) {
                        PA_SetObjectVariable(result, newRef());
                    } else {
                        Text key = text(ascii);
                        *result = copyVariable(refs.at(static_cast<void*>(args[0]->uValue.fObject))->values.at(key));
                    }
                    break;
                default:
                    require(false, "unexpected command");
            }
            break;
        }
        default:
            require(false, "unexpected engine selector");
    }
}

void setRaw(void* obj, const PA_Unichar* keyText, PA_Variable value) {
    PA_Unistring key = PA_CreateUnistring(const_cast<PA_Unichar*>(keyText));
    PA_SetObjectProperty(obj, &key, value);
    PA_DisposeUnistring(&key);
}

void checkProperty(void* obj, const PA_Unichar* expected) {
    PA_Unistring key = PA_CreateUnistring(const_cast<PA_Unichar*>(ascii));
    PA_Variable result = PA_GetObjectProperty(obj, &key);
    require(PA_GetLastError() == eER_NoErr, "property read failed");
    PA_Unistring borrowed = PA_GetStringVariable(result);
    require(readString(borrowed) == text(expected), "setter exact text mismatch");
    PA_ClearVariable(&result);
    PA_DisposeUnistring(&key);
}

void setters() {
    for (bool nullRepresentation : {false, true}) {
        nullEmpty = nullRepresentation;
        for (size_t i = 0; i < 4; ++i) {
            void* obj = newRef();
            Text u16 = text(fixtures[i]);
            for (int variant = 0; variant < 4; ++variant) {
                for (bool rejected : {false, true}) {
                    failSet = rejected;
                    switch (variant) {
                        case 0: ob_set_s(obj, "Alias", utf8[i]); break;
                        case 1: ob_set_s(obj, L"Alias", utf8[i]); break;
                        case 2: ob_set_a(obj, L"Alias", wide[i]); break;
                        case 3: ob_set_a(obj, L"Alias", &u16); break;
                    }
                    failSet = false;
                    checkProperty(obj, fixtures[i]);
                }
            }
            PA_DisposeObject(obj);
            balanced("string setter leaked initial allocated empty owner");
        }
    }
}

void scalars() {
    for (bool nullRepresentation : {false, true}) {
        nullEmpty = nullRepresentation;
        for (size_t i = 0; i < 4; ++i) {
            void* obj = newRef();
            PA_Variable input = {};
            PA_Unistring owned = PA_CreateUnistring(const_cast<PA_Unichar*>(fixtures[i]));
            PA_SetStringVariable(&input, &owned);
            setRaw(obj, ascii, input);
            PA_ClearVariable(&input);
            CUTF8String output;
            require(ob_get_a(obj, L"Alias", &output), "string getter lost existence result");
            require(output == CUTF8String(reinterpret_cast<const uint8_t*>(utf8[i])), "getter exact UTF-8 mismatch");
            require(!ob_get_b(obj, L"Alias"), "boolean mismatch default");
            require(ob_get_n(obj, L"Alias") == 0, "number mismatch default");
            PA_DisposeObject(obj);
            balanced("scalar getter leaked owning property result");
        }
        void* obj = newRef();
        PA_Variable input = {};
        PA_SetBooleanVariable(&input, 1);
        setRaw(obj, ascii, input);
        require(ob_get_b(obj, L"Alias"), "boolean value mismatch");
        PA_SetRealVariable(&input, 3.25);
        setRaw(obj, ascii, input);
        require(ob_get_n(obj, L"Alias") == 3.25, "number value mismatch");
        PA_DisposeObject(obj);
        balanced("scalar getter cleanup imbalance");
    }
}

void references() {
    for (int kind : {eVK_Object, eVK_Collection}) {
        void* obj = newRef();
        void* child = newRef();
        PA_Variable input = {};
        if (kind == eVK_Object) PA_SetObjectVariable(&input, child);
        else PA_SetCollectionVariable(&input, child);
        setRaw(obj, ascii, input);
        PA_ClearVariable(&input);
        CUTF8String unused;
        ob_get_a(obj, L"Alias", &unused);
        ob_get_b(obj, L"Alias");
        ob_get_n(obj, L"Alias");
        void* handoff;
        if (kind == eVK_Object) {
            require(ob_get_c(obj, L"Alias") == nullptr, "collection mismatch");
            handoff = ob_get_o(obj, L"Alias");
        } else {
            require(ob_get_o(obj, L"Alias") == nullptr, "object mismatch");
            handoff = ob_get_c(obj, L"Alias");
        }
        PA_DisposeObject(obj);
        require(handoff == child && refs.count(child), "owning handoff did not survive parent destruction");
        require(refs.at(child)->owners == 1, "reference getter leaked mismatch owner");
        if (kind == eVK_Object) PA_DisposeObject(handoff);
        else PA_DisposeCollection(handoff);
        balanced("owning reference handoff cleanup imbalance");
    }
    void* obj = newRef();
    PA_Variable input = {};
    PA_Unistring str = PA_CreateUnistring(const_cast<PA_Unichar*>(ascii));
    PA_SetStringVariable(&input, &str);
    setRaw(obj, ascii, input);
    PA_ClearVariable(&input);
    require(!ob_get_c(obj, L"Alias") && !ob_get_o(obj, L"Alias"), "reference/string mismatch");
    PA_DisposeObject(obj);
    balanced("reference getter leaked mismatched string result");

    void* collection = newRef();
    PA_SetBooleanVariable(&input, 1);
    refs.at(collection)->values[Text()] = input;
    PA_Variable element = PA_GetCollectionElement(collection, 0);
    require(PA_GetLastError() == eER_NoErr && PA_GetBooleanVariable(element), "collection element contract");
    PA_ClearVariable(&element);
    PA_DisposeCollection(collection);
    balanced("collection element cleanup imbalance");
}

void failed() {
    void* obj = newRef();
    PA_Variable input = {};
    PA_SetBooleanVariable(&input, 1);
    setRaw(obj, ascii, input);
    failGet = true;
    CUTF8String output;
    require(!ob_get_a(obj, L"Alias", &output), "failed string getter reported success");
    require(!ob_get_b(obj, L"Alias") && ob_get_n(obj, L"Alias") == 0, "failed scalar defaults");
    require(!ob_get_o(obj, L"Alias") && !ob_get_c(obj, L"Alias"), "failed reference defaults");
    require(failedGets == 5, "failed getter coverage");
    failGet = false;
    PA_DisposeObject(obj);
    balanced("failed getter touched unspecified output or leaked key");
}

void arrays() {
    for (bool nullRepresentation : {false, true}) {
        nullEmpty = nullRepresentation;
        PA_Variable arr = PA_CreateVariable(eVK_ArrayUnicode);
        PA_ResizeArray(&arr, 3);
        for (int i = 0; i < 4; ++i) {
            PA_Unistring owned = PA_CreateUnistring(const_cast<PA_Unichar*>(fixtures[i]));
            PA_SetStringInArray(arr, i, &owned);
            require(readString(PA_GetStringInArray(arr, i)) == text(fixtures[i]), "accepted transfer exact text");
        }
        PA_Unistring borrowed = PA_GetStringInArray(arr, 2);
        PA_Unistring independent = PA_CreateUnistring(borrowed.fString);
        PA_SetStringInArray(arr, 1, &independent);
        PA_Unistring replacement = PA_CreateUnistring(const_cast<PA_Unichar*>(ascii));
        PA_SetStringInArray(arr, 2, &replacement);
        require(readString(PA_GetStringInArray(arr, 1)) == text(supplementary), "borrowed independent copy lost content");
        for (int rejection = 0; rejection < 5; ++rejection) {
            PA_Variable destination = arr;
            int index = 1;
            if (rejection == 0) destination.fType = eVK_Longint;
            if (rejection == 1) destination.uValue.fArray.fData = nullptr;
            if (rejection == 2) index = -1;
            if (rejection == 3) index = 4;
            PA_Unistring owned = PA_CreateUnistring(const_cast<PA_Unichar*>(ascii));
            PA_SetStringInArray(destination, index, rejection == 4 ? nullptr : &owned);
            require(readString(owned) == text(ascii), "rejected transfer consumed input");
            PA_DisposeUnistring(&owned);
        }
        C_TEXT scalar;
        PA_Unistring input = PA_GetStringInArray(arr, 1);
        scalar.setUTF16String(&input);
        ARRAY_TEXT copy;
        BytePtr parameters[] = {reinterpret_cast<BytePtr>(&arr)};
        copy.fromParamAtIndex(parameters, 1);
        PA_ResizeArray(&arr, 0);
        PA_ClearVariable(&arr);
        CUTF16String result;
        copy.copyUTF16StringAtIndex(&result, 1);
        require(result == text(supplementary), "wrapper retained borrowed array storage");
        PA_Variable out = PA_CreateVariable(eVK_Undefined);
        parameters[0] = reinterpret_cast<BytePtr>(&out);
        copy.toParamAtIndex(parameters, 1);
        copy.toParamAtIndex(parameters, 1);
        require(readString(PA_GetStringInArray(out, 1)) == text(supplementary), "wrapper replacement lost copied text");
        PA_ClearVariable(&out);
        PA_Unistring returned = PA_CreateUnistring(const_cast<PA_Unichar*>(empty));
        PA_Unistring* returnPtr = &returned;
        scalar.setReturn(reinterpret_cast<sLONG_PTR*>(&returnPtr));
        scalar.setUTF16String(ascii, 5);
        require(readString(returned) == text(supplementary), "content setter aliased wrapper storage");
        PA_DisposeUnistring(&returned);
        balanced("array/scalar string or handle balance");
    }
}

void stringify() {
    for (size_t i = 0; i < 4; ++i) {
        void* obj = newRef();
        PA_Variable input = {};
        PA_Unistring owned = PA_CreateUnistring(const_cast<PA_Unichar*>(fixtures[i]));
        PA_SetStringVariable(&input, &owned);
        setRaw(obj, ascii, input);
        PA_ClearVariable(&input);
        CUTF8String output;
        ob_stringify(obj, &output);
        require(output == CUTF8String(reinterpret_cast<const uint8_t*>(utf8[i])), "stringify exact text");
        mismatchStringify = true;
        ob_stringify(obj, &output);
        mismatchStringify = false;
        failStringify = true;
        ob_stringify(obj, &output);
        failStringify = false;
        PA_DisposeObject(obj);
        balanced("stringify result or independent argument leak");
    }
}
}

extern "C" void PluginMain(PA_long32, PA_PluginParameters) {}

int main(int argc, char** argv) {
    require(argc == 2, "expected case name");
    gCall4D = engine;
    std::string name = argv[1];
    if (name == "setters") setters();
    else if (name == "scalars") scalars();
    else if (name == "references") references();
    else if (name == "failed") failed();
    else if (name == "arrays") arrays();
    else if (name == "stringify") stringify();
    else require(false, "unknown case");
    balanced("final ownership balance");
    std::cout << "PASS " << name << '\n';
}
