import argparse
import histlang

parser = argparse.ArgumentParser(description="Apply sound changes to a wordlist.")

parser.add_argument("sc_path", type=str, help="Path to the sound change file.")
parser.add_argument("word_path", type=str, help="Path to the wordlist file.")
parser.add_argument("output_path", type=str, help="Path to the output file.")


if __name__ == "__main__":
    args = parser.parse_args()
    sc = histlang.tokenize_sound_changes(open(args.sc_path, encoding="utf-8").read())
    words = histlang.tokenize_words(open(args.word_path, encoding="utf-8").read())
    outputs = [histlang.apply_sound_changes(word, sc) for word in words]
    open(args.output_path, "w", encoding="utf-8").write("\n".join(map(str, outputs)))

