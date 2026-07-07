// Tiny, compiler-version-agnostic smoke target for the toolchain matrix.
// Deliberately does not include any PyTorch header: this suite's job is to
// isolate whether a *toolchain version* regresses codegen, not to revalidate
// the real-header checks the primary riscv64.yml suites already own.
#include <cstdint>
#include <cstdio>

static uint64_t fnv1a(const char *s) {
  uint64_t h = 1469598103934665603ull;
  for (; *s; ++s) {
    h ^= static_cast<unsigned char>(*s);
    h *= 1099511628211ull;
  }
  return h;
}

int main() {
  const uint64_t expected = 0x4d4d360409fe140aull; // fnv1a("riscv-toolchain-matrix")
  const uint64_t actual = fnv1a("riscv-toolchain-matrix");
  if (actual != expected) {
    std::fprintf(stderr, "codegen mismatch: got %llu want %llu\n",
                 static_cast<unsigned long long>(actual),
                 static_cast<unsigned long long>(expected));
    return 2;
  }
  std::printf("toolchain_smoke_ok hash=%llu\n", static_cast<unsigned long long>(actual));
  return 0;
}
