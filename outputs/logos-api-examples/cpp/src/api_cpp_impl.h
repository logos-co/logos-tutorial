#pragma once
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
#include <logos_json.h>
#include <logos_result.h>
#include <logos_module_context.h>

struct Entry {
    std::string label;
    std::vector<uint8_t> payload;
    std::optional<uint64_t> count;
};
struct Batch {
    Entry entry;
    std::vector<std::string> tags;
};

class ApiCppImpl : public LogosModuleContext {
public:
    std::string echoString(const std::string& v);
    std::vector<uint8_t> echoBytes(const std::vector<uint8_t>& v);
    int64_t echoInt(int64_t v);
    uint64_t echoUint(uint64_t v);
    double echoDouble(double v);
    bool echoBool(bool v);
    nlohmann::json echoAny(const nlohmann::json& v);
    std::vector<std::string> echoStringList(const std::vector<std::string>& v);
    std::vector<int64_t> echoIntList(const std::vector<int64_t>& v);
    std::vector<uint64_t> echoUintList(const std::vector<uint64_t>& v);
    std::vector<double> echoDoubleList(const std::vector<double>& v);
    std::vector<bool> echoBoolList(const std::vector<bool>& v);
    LogosList echoList(const LogosList& v);
    LogosMap echoMap(const LogosMap& v);
    std::vector<std::vector<uint8_t>> echoBytesList(const std::vector<std::vector<uint8_t>>& v);
    std::map<std::string, std::vector<uint8_t>> echoBytesMap(const std::map<std::string, std::vector<uint8_t>>& v);
    std::map<std::string, int64_t> echoIntMap(const std::map<std::string, int64_t>& v);
    std::unordered_map<std::string, int64_t> echoUnorderedMap(const std::unordered_map<std::string, int64_t>& v);
    std::vector<std::vector<int64_t>> echoNested(const std::vector<std::vector<int64_t>>& v);
    Entry echoEntry(const Entry& v);
    std::vector<Entry> echoEntries(const std::vector<Entry>& v);
    std::map<std::string, Entry> echoEntryMap(const std::map<std::string, Entry>& v);
    Batch echoBatch(const Batch& v);
    std::optional<std::string> echoOptional(const std::optional<std::string>& v);
    void doVoid();
    StdLogosResult makeResult(bool ok);
    int64_t slow(int64_t ms);
    std::string checkCalls(const std::string& provider);
    std::string startAsync(const std::string& provider);
    std::string asyncStatus();
};
