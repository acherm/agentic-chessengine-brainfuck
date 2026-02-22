/*
 * bfi.c - Brainfuck interpreter for BFChess
 *
 * Features:
 *   - 8-bit wrapping cells (unsigned char)
 *   - 65536-cell tape
 *   - EOF returns 0
 *   - Flushes stdout after each '\n' output
 *   - Precomputed bracket jump table for speed
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TAPE_SIZE 65536
#define MAX_PROGRAM (16 * 1024 * 1024)  /* 16 MB max BF program */

static unsigned char tape[TAPE_SIZE];
static int *jump;  /* precomputed bracket targets */

int main(int argc, char *argv[]) {
    FILE *fp;
    char *prog;
    long prog_len;
    int dp = 0;  /* data pointer */
    long ip = 0; /* instruction pointer */

    if (argc < 2) {
        fprintf(stderr, "Usage: %s <program.bf>\n", argv[0]);
        return 1;
    }

    /* Read program */
    fp = fopen(argv[1], "r");
    if (!fp) {
        fprintf(stderr, "Error: cannot open '%s'\n", argv[1]);
        return 1;
    }

    prog = (char *)malloc(MAX_PROGRAM);
    if (!prog) {
        fprintf(stderr, "Error: out of memory\n");
        fclose(fp);
        return 1;
    }

    /* Load only BF instructions */
    prog_len = 0;
    {
        int c;
        while ((c = fgetc(fp)) != EOF && prog_len < MAX_PROGRAM - 1) {
            if (c == '>' || c == '<' || c == '+' || c == '-' ||
                c == '.' || c == ',' || c == '[' || c == ']') {
                prog[prog_len++] = (char)c;
            }
        }
    }
    prog[prog_len] = '\0';
    fclose(fp);

    /* Allocate jump table */
    jump = (int *)calloc(prog_len, sizeof(int));
    if (!jump) {
        fprintf(stderr, "Error: out of memory for jump table\n");
        free(prog);
        return 1;
    }

    /* Build jump table for brackets */
    {
        int *stack = (int *)malloc(prog_len * sizeof(int));
        int sp = 0;
        long i;
        for (i = 0; i < prog_len; i++) {
            if (prog[i] == '[') {
                stack[sp++] = (int)i;
            } else if (prog[i] == ']') {
                if (sp <= 0) {
                    fprintf(stderr, "Error: unmatched ']' at position %ld\n", i);
                    free(prog);
                    return 1;
                }
                sp--;
                jump[stack[sp]] = (int)i;
                jump[i] = stack[sp];
            }
        }
        if (sp != 0) {
            fprintf(stderr, "Error: unmatched '[' (%d open)\n", sp);
            free(stack);
            free(prog);
            return 1;
        }
        free(stack);
    }

    /* Execute */
    memset(tape, 0, sizeof(tape));

    while (ip < prog_len) {
        switch (prog[ip]) {
        case '>':
            dp = (dp + 1) & (TAPE_SIZE - 1);
            break;
        case '<':
            dp = (dp - 1) & (TAPE_SIZE - 1);
            break;
        case '+':
            tape[dp]++;
            break;
        case '-':
            tape[dp]--;
            break;
        case '.':
            putchar(tape[dp]);
            if (tape[dp] == '\n')
                fflush(stdout);
            break;
        case ',':
            {
                int c = getchar();
                tape[dp] = (c == EOF) ? 0 : (unsigned char)c;
            }
            break;
        case '[':
            if (tape[dp] == 0)
                ip = jump[ip];
            break;
        case ']':
            if (tape[dp] != 0)
                ip = jump[ip];
            break;
        }
        ip++;
    }

    free(jump);
    free(prog);
    return 0;
}
