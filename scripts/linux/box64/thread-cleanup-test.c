#define _GNU_SOURCE
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Call the same glibc entry point as C++ thread_local objects, without libstdc++ dependencies. */
extern int __cxa_thread_atexit_impl(void (*destructor)(void *), void *object, void *dso);
extern void *__dso_handle;
static pthread_barrier_t barrier;
static atomic_int calls;
static _Thread_local int owner, next;
enum { THREADS = 24, REGISTRATIONS = 512 };

static void cleanup(void *arg) {
    uintptr_t value = (uintptr_t)arg;
    int expectedOwner = (int)(value >> 16);
    int index = (int)(value & 65535);
    if (owner != expectedOwner || next != index) {
        fprintf(stderr, "FAIL: destructor owner=%d/%d order=%d/%d\n", owner, expectedOwner, next, index);
        _Exit(12);
    }
    --next;
    atomic_fetch_add(&calls, 1);
}

static void *worker(void *arg) {
    owner = (int)(uintptr_t)arg;
    next = REGISTRATIONS - 1;
    pthread_barrier_wait(&barrier);
    for (int i = 0; i < REGISTRATIONS; ++i)
        if (__cxa_thread_atexit_impl(cleanup, (void *)(((uintptr_t)owner << 16) | i), __dso_handle)) _Exit(13);
    return NULL;
}

static int mainDestructor;
static void finish(void) {
    if (mainDestructor != 2) { fputs("FAIL: main-thread cleanup did not run before atexit\n", stderr); _Exit(14); }
    puts("PASS: main-thread and reentrant cleanup before process atexit");
}
static void nested(void *arg) { (void)arg; ++mainDestructor; }
static void mainCleanup(void *arg) {
    (void)arg;
    ++mainDestructor;
    if (__cxa_thread_atexit_impl(nested, NULL, __dso_handle)) _Exit(15);
}

int main(int argc, char **argv) {
    setbuf(stdout, NULL);
    if (argc > 1 && !strcmp(argv[1], "main")) {
        atexit(finish);
        return __cxa_thread_atexit_impl(mainCleanup, NULL, __dso_handle);
    }
    int count = argc > 1 && !strcmp(argv[1], "serial") ? 1 : THREADS;
    pthread_t threads[THREADS];
    if (pthread_barrier_init(&barrier, NULL, count)) return 16;
    for (int i = 0; i < count; ++i) if (pthread_create(&threads[i], NULL, worker, (void *)(uintptr_t)(i + 1))) return 17;
    for (int i = 0; i < count; ++i) if (pthread_join(threads[i], NULL)) return 18;
    if (atomic_load(&calls) != count * REGISTRATIONS) {
        fprintf(stderr, "FAIL: only %d/%d destructors ran at thread exit\n", atomic_load(&calls), count * REGISTRATIONS);
        _Exit(19);
    }
    pthread_barrier_destroy(&barrier);
    printf("PASS: %d destructors on %d owning threads, reverse order, before join returns\n", atomic_load(&calls), count);
    return 0;
}
