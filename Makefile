.PHONY: all clean test generate play

all: bfi chess.bf

bfi: bfi.c
	clang -O2 -o bfi bfi.c

chess.bf: generate.py bf_emitter.py bf_memory.py bf_primitives.py bf_io.py bf_chess.py bf_movegen.py bf_uci.py
	python3 generate.py

generate: chess.bf

test: bfi
	pytest tests/ -v

handshake: bfi chess.bf
	echo "uci\nisready\nquit" | ./bfi chess.bf

singlemove: bfi chess.bf
	echo "uci\nisready\nposition startpos\ngo\nquit" | ./bfi chess.bf

clean:
	rm -f bfi chess.bf
