/*
 * testapp.c — integration-test binary for ghidra-rpc
 *
 * Compiled to tests/fixtures/testapp (x86-64 ELF, dynamically linked).
 * Kept in the repository as a stable, reproducible test fixture.
 *
 * Compile:
 *   gcc -O0 -m64 -o tests/fixtures/testapp tests/fixtures/testapp.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Simple linked-list stack ───────────────────────────────────────────── */

typedef struct Node {
    int          value;
    struct Node *next;
} Node;

static Node *node_alloc(int value)
{
    Node *n = (Node *)malloc(sizeof(Node));
    if (!n) {
        fprintf(stderr, "node_alloc: hello from malloc failure path\n");
        return NULL;
    }
    n->value = value;
    n->next  = NULL;
    return n;
}

Node *stack_push(Node *head, int v)
{
    Node *n = node_alloc(v);
    if (!n) return head;
    n->next = head;
    return n;
}

Node *stack_pop(Node *head, int *out)
{
    if (!head) return NULL;
    *out       = head->value;
    Node *next = head->next;
    free(head);
    return next;
}

void stack_free(Node *head)
{
    while (head) {
        Node *next = head->next;
        free(head);
        head = next;
    }
}

/* ── Arithmetic helpers ─────────────────────────────────────────────────── */

long factorial(int n)
{
    if (n <= 1) return 1L;
    return (long)n * factorial(n - 1);
}

int sum_array(const int *arr, int len)
{
    int total = 0;
    for (int i = 0; i < len; i++)
        total += arr[i];
    return total;
}

/* ── String helpers ─────────────────────────────────────────────────────── */

char *str_dup_upper(const char *s)
{
    size_t len = strlen(s);
    char  *buf = (char *)malloc(len + 1);
    if (!buf) return NULL;
    for (size_t i = 0; i < len; i++)
        buf[i] = (s[i] >= 'a' && s[i] <= 'z') ? (char)(s[i] - 32) : s[i];
    buf[len] = '\0';
    return buf;
}

int count_char(const char *s, char c)
{
    int count = 0;
    while (*s)
        if (*s++ == c) count++;
    return count;
}

/* ── Greeting helpers ───────────────────────────────────────────────────── */

void greet_formal(const char *name)
{
    printf("Hello, %s. Welcome to the integration test.\n", name);
}

void greet_casual(const char *name)
{
    printf("Hello %s! Running integration tests now.\n", name);
}

/* ── Entry point ────────────────────────────────────────────────────────── */

int main(int argc, char *argv[])
{
    (void)argc;

    /* Greet */
    greet_formal("Ghidra");
    greet_casual("World");

    /* Factorial */
    for (int i = 1; i <= 6; i++)
        printf("factorial(%d) = %ld\n", i, factorial(i));

    /* Stack push/pop */
    Node *stack = NULL;
    for (int i = 0; i < 4; i++)
        stack = stack_push(stack, i * 11);

    int v;
    while (stack)
        stack = stack_pop(stack, &v);

    /* sum_array */
    int nums[] = {3, 1, 4, 1, 5, 9, 2, 6};
    printf("sum = %d\n", sum_array(nums, 8));

    /* String operations */
    const char *msg = "integration test binary for ghidra-rpc";
    char       *upper = str_dup_upper(msg);
    if (upper) {
        printf("upper: %s\n", upper);
        free(upper);
    }

    printf("count 'e' in msg: %d\n", count_char(msg, 'e'));

    /* strcmp usage (ensures the import appears) */
    if (strcmp(argv[0], "") != 0)
        printf("program: %s\n", argv[0]);

    return 0;
}
