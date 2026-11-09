# Graph tools per stack — hints, not requirements

The structure sub-agent uses this list at fallback level 3, after checking what the repo and its
toolchain already provide: run a dedicated tool only if it is already
installed, otherwise recommend it in the evidence file's Unknowns. Every tool
here has blind spots; copy the relevant ones into Unknowns too.

| Stack         | Toolchain-native (no install)                          | Dedicated tools                                            | Known blind spots                                                                 |
| ------------- | ------------------------------------------------------ | ---------------------------------------------------------- | --------------------------------------------------------------------------------- |
| JS / TS       | —                                                      | dependency-cruiser, madge, skott                           | path aliases if tsconfig is not wired; dynamic `import()`; re-exports             |
| Python        | —                                                      | Tach (`tach show`), pydeps (`--show-dot`, `--show-cycles`) | dynamic imports, plugins via entry points, `importlib`                            |
| Java          | `jdeps --dot-output`, `mvn dependency:tree`            | NDepend (commercial)                                       | reflection, `Class.forName`, DI containers                                        |
| Go            | `go list -deps -json ./...`, `go mod graph`            | goda (`goda graph ./...`)                                  | module boundaries not detected automatically by goda; interfaces wired at runtime |
| C# / .NET     | `dotnet list reference`                                | dotnet-deptree, NDepend                                    | reflection, DI registration, source generators                                    |
| Swift         | `swift package show-dependencies --format json`        | spmgraph                                                   | Xcode-project targets outside SwiftPM                                             |
| Kotlin/Gradle | `gradle dependencies`                                  | gradle-dependency-graph-generator, modules-graph-assert    | module-level only; reflection and DI                                              |
| Rust          | `cargo metadata`, `cargo tree`                         | cargo-modules                                              | crate-level by default; macros and feature flags                                  |
| Any           | `ast-grep` / `rg` import extraction (fallback level 4) | —                                                          | unresolved aliases, re-exports, anything not written as an import                 |

Notes that apply to every tool:

- Exclude external packages completely. For dependency-cruiser,
  `doNotFollow: node_modules` still draws packages as leaf nodes — use
  `--exclude` (or remove them when converting to the edge list).
- Exclude tests, stories, snapshots and generated code from the graph unless
  the question is about them.
- A static graph never shows dependencies injected at runtime: dynamic
  require, build-time injection, feature flags, codegen. These gaps belong in
  the map.
