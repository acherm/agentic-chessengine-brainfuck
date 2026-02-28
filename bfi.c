/*
 * bfi.c - Brainfuck interpreter for BFChess
 *
 * Features:
 *   - 8-bit wrapping cells (unsigned char)
 *   - 65536-cell tape
 *   - EOF returns 0
 *   - Flushes stdout after each '\n' output
 *   - RLE compilation: consecutive ><+- collapsed into single instructions
 *   - Precomputed bracket jump table on compiled instruction array
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TAPE_SIZE 65536
#define MAX_PROGRAM (16 * 1024 * 1024)  /* 16 MB max BF program */

typedef struct {
    char op;   /* '>', '<', '+', '-', '.', ',', '[', ']' */
    int  arg;  /* count for ><+-, jump index for [] */
} Instr;

static unsigned char tape[TAPE_SIZE];

int main(int argc, char *argv[]) {
    FILE *fp;
    char *raw;
    long raw_len;
    Instr *ops;
    int num_ops;
    int dp = 0;  /* data pointer */
    int ip = 0;  /* instruction pointer */

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

    raw = (char *)malloc(MAX_PROGRAM);
    if (!raw) {
        fprintf(stderr, "Error: out of memory\n");
        fclose(fp);
        return 1;
    }

    /* Load only BF instructions */
    raw_len = 0;
    {
        int c;
        while ((c = fgetc(fp)) != EOF && raw_len < MAX_PROGRAM - 1) {
            if (c == '>' || c == '<' || c == '+' || c == '-' ||
                c == '.' || c == ',' || c == '[' || c == ']') {
                raw[raw_len++] = (char)c;
            }
        }
    }
    fclose(fp);

    /* Phase 1: RLE compress into Instr array */
    ops = (Instr *)malloc(raw_len * sizeof(Instr));
    if (!ops) {
        fprintf(stderr, "Error: out of memory for ops\n");
        free(raw);
        return 1;
    }

    num_ops = 0;
    {
        long i = 0;
        while (i < raw_len) {
            char ch = raw[i];
            if (ch == '>' || ch == '<' || ch == '+' || ch == '-') {
                int count = 1;
                while (i + count < raw_len && raw[i + count] == ch)
                    count++;
                ops[num_ops].op = ch;
                ops[num_ops].arg = count;
                num_ops++;
                i += count;
            } else {
                /* '.', ',', '[', ']' — not collapsed */
                ops[num_ops].op = ch;
                ops[num_ops].arg = 0;
                num_ops++;
                i++;
            }
        }
    }
    free(raw);

    /* Shrink allocation */
    ops = (Instr *)realloc(ops, num_ops * sizeof(Instr));

    fprintf(stderr, "RLE: %ld raw -> %d instructions (%.1fx compression)\n",
            raw_len, num_ops, (double)raw_len / num_ops);

    /* Phase 2: Build jump table for brackets on Instr array */
    {
        int *stack = (int *)malloc(num_ops * sizeof(int));
        int sp = 0;
        int i;
        for (i = 0; i < num_ops; i++) {
            if (ops[i].op == '[') {
                stack[sp++] = i;
            } else if (ops[i].op == ']') {
                if (sp <= 0) {
                    fprintf(stderr, "Error: unmatched ']' at instruction %d\n", i);
                    free(ops);
                    free(stack);
                    return 1;
                }
                sp--;
                ops[stack[sp]].arg = i;
                ops[i].arg = stack[sp];
            }
        }
        if (sp != 0) {
            fprintf(stderr, "Error: unmatched '[' (%d open)\n", sp);
            free(stack);
            free(ops);
            return 1;
        }
        free(stack);
    }

    /* Phase 3: Execute */
    memset(tape, 0, sizeof(tape));

    while (ip < num_ops) {
        switch (ops[ip].op) {
        case '>':
            dp = (dp + ops[ip].arg) & (TAPE_SIZE - 1);
            break;
        case '<':
            dp = (dp - ops[ip].arg) & (TAPE_SIZE - 1);
            break;
        case '+':
            tape[dp] += (unsigned char)ops[ip].arg;
            break;
        case '-':
            tape[dp] -= (unsigned char)ops[ip].arg;
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
                ip = ops[ip].arg;
            break;
        case ']':
            if (tape[dp] != 0)
                ip = ops[ip].arg;
            break;
        }
        ip++;
    }

    free(ops);
    return 0;
}
