#include <emacs-module.h>
int plugin_is_GPL_compatible;
static emacs_value answer(emacs_env *env, ptrdiff_t n, emacs_value *args, void *data) {
    (void)n; (void)args; (void)data;
    return env->make_integer(env, 42);
}
int emacs_module_init(struct emacs_runtime *runtime) {
    emacs_env *env = runtime->get_environment(runtime);
    emacs_value f = env->make_function(env, 0, 0, answer, "External module test.", 0);
    emacs_value args[] = {env->intern(env, "portable-module-answer"), f};
    env->funcall(env, env->intern(env, "fset"), 2, args);
    return env->non_local_exit_check(env) != emacs_funcall_exit_return;
}
