# Kinesis Firehose Conversion Lambdas

These Lambdas are common transformations that might be applied to a Firehose delivery
stream, as well as acting as a base for new transformations.

* `newline_transform` ensures that records will have a newline separating them. It
  removes any existing newlines or carriage-returns at the end of the input record
  and appends a single newline.

* `json_transform` ensures that the output file consists of single-line JSON text
  records, separated by newlines. Source records that are GZipped are uncompressed,
  those that can't be parsed are reported, and there's a hook that lets you drop
  records based on their contents.
