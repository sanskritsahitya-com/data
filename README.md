This repository hosts all the data that powers [SanskritSahitya.org](https://sanskritsahitya.org).

The structure of the repo is straightforward:
* `code/` holds any scripts that might be useful for reading / writing this data
* For a typical Kaavya named `kaavya`, there would be file `kavya/kaavya.json` that has the entire text of the Kaavya.

For large kaavyas such as the Mahabharatam, the data has been sharded, with the number appended to the filename. eg. `mahabharatam/mahabharatam1.json` etc.


The typical structure of the JSON is:
```
{
    "title": "Name of the Kaavya",
    "books": [{"number": "1", "name": "Name of Book 1"},
              {"number": "2", "name": "Name of Book 2"}, ...]
    "chapters": [{"number": "1", "name": "Name of Chapter 1"},
                 {"number": "2", "name": "Name of Chapter 2"}, ...]
    "data": [
        {"c": "1", "n": "1", "i": 0, "v": "Shlok 1.1"},
        {"c": "1", "n": "2", "i": 1, "v": "Shlok 1.2"},
        ...
    ]
}
```

The format currently supports _kaavyas_ that are either:
* Not sub-divided into chapters / sections. A _shloka_ in such a _kaavya_ is referenced with just the number of the _shloka_. Example `/meghadutam/1`.
* Divided into sections / chapters that comprise of shlokas. A _shloka_ in such a _kaavya_ is referenced with the chapter number combined with the _shloka_ number. Example `/raghuvansham/1.1`.
* Divided into books which are sub-divided into sections, which then comprise of shlokas. A chapter in such a _kaavya_ is referenced with the book number and chapter number combined (e.g. `1.1`) and a _shloka_ is represented with all three combined. Example `/mahabharatam/1.1.1`.

The `data` key has a list of objects (referred to as `Shloka` objects) representing the entire text.

The structure of a `Shloka` object is:

```
{
    // [String] Chapter number, matches the chapter numbers declared in the `chapters` key.
    // For Kaavyas with books, this would include the book number.
    "c": "1",

    // [String] Shloka number
    "n": "1",

    // [Integer] Index. This represents the overall index of this shloka / line
    // in the text, and runs monotonically from start to end.
    "i": 0,

    // [String] Verse [Shloka]. The actual text of the shloka.
    "v": "वागर्थाविव संपृक्तौ..."

    // [String] Text. Refers to non-shloka text such as 'धृतराष्ट्र उवाच ।' that is
    // meant to be interspersed with shlokas.
    // A Shloka object should have only one of |v| and |t| keys.
    // A text entry doesn't have the "n" or "i" keys present.
    "t": "धृतराष्ट्र उवाच ।"

    // [String] Speaker. This is used in plays to annotate the speaker of this particular text.
    // Using this makes it easier to show the speaker in the UI and allows searching for dialogues
    // based on speakers.
    "sp": "शकुन्तला"
}
```

The focus is to make this easy to access through computational means, but it's written out in a specifically pretty-printed JSON format to be relatively easily human readable and to lead to clean diffs when modifying any line. It is still a pure JSON object that can be read by any parser, but if you are planning to submit changes to the repository, run `python3 code/linter.py` to ensure all files are formatted correctly. 

