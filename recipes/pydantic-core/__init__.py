"""pydantic-core, built for Android with maturin.

Identical to p4a's builtin recipe (same version, same Rust cross-compile via
RustCompiledComponentsRecipe) with one addition: the environment handed to
`python -m build`.

Why it is needed: PyProjectRecipe builds the wheel through PEP 517, and the
environment it passes is `arch.get_env()` — built from scratch, not from the
caller's os.environ. So an ANDROID_API_LEVEL exported in CI never arrives, and
maturin 1.16 aborts the wheel step with

    Failed to determine Android API level. Please set the ANDROID_API_LEVEL
    environment variable.

after cargo has already compiled pydantic-core successfully. p4a's
RustCompiledComponentsRecipe supplies the cargo linker and the PYO3_CROSS_*
vars but not these three, which is what this override adds.

Keep `version` equal to the `pydantic==` pin in buildozer.spec: pydantic
refuses to load when pydantic-core is not the exact version it requires.
"""

from pythonforandroid.recipe import RustCompiledComponentsRecipe


class PydanticcoreRecipe(RustCompiledComponentsRecipe):
    version = "2.41.4"
    url = "https://github.com/pydantic/pydantic-core/archive/refs/tags/v{version}.tar.gz"
    site_packages_name = "pydantic_core"

    def get_recipe_env(self, arch=None, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["ANDROID_API_LEVEL"] = str(self.ctx.ndk_api)
        env["ANDROID_NDK_HOME"] = self.ctx.ndk_dir
        env["ANDROID_NDK_ROOT"] = self.ctx.ndk_dir
        return env


recipe = PydanticcoreRecipe()
