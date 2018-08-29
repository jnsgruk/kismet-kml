### Kismet KML/JSON Generator

This is a parser that takes \*.kismet files generated by the latest version of [Kismet](https://github.com/kismetwireless/kismet) and returns a colour coded KML file, and a JSON file in a bespoke format used by my other project, [Monza](https://github.com/jnsgruk/monza).

To install dependencies, run the following:

```
$ git clone https://github.com/jnsgruk/kismet-kml
$ cd kismet-kml/
$ pip install -r requirements.txt
```

You're now ready to parse Kismet files like so:

```
$ python3 main.py -i <path to Kismet file> -k <output KML path> -j <output JSON path>
```

You can optionally pass `-p` to print out the JSON to stdout.
