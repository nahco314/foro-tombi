rustup target add ${DLL_PACK_TARGET}

cargo build --profile super-release --target ${DLL_PACK_TARGET}

mkdir ./artifacts/

LD_LIBRARY_PATH=$(rustc --print sysroot)/lib/rustlib/$(rustc -vV | grep host | awk '{print $2}')/lib \
    dll-pack-builder local $(cargo metadata --no-deps --format-version 1 | jq -r '.packages[0].name') \
    $(dll-pack-builder find ${BUILD_OUT_DIR}) \
    ./artifacts/ ${DLL_PACK_TARGET} ${GITHUB_REPOSITORY} ${GITHUB_REF#refs/tags/} \
    --include "$(rustc --print sysroot | sed 's|\\|/|g')/lib/rustlib/$(rustc -vV | grep host | awk '{print $2}')/lib/*" \
    --macho-rpath $(rustc --print sysroot)/lib/rustlib/$(rustc -vV | grep host | awk '{print $2}')/lib \
    --win-path $(rustc --print sysroot)/lib/rustlib/$(rustc -vV | grep host | awk '{print $2}')/lib
