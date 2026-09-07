The `datasette/` directory holds a checkout of Datasette, a tool for exploring
and publishing SQLite databases over HTTP. Table and query results can already
be downloaded in several formats — `.json` is built in, `.csv` is built in — via
its output-renderer plugin hook.

Write a design document for adding a **Parquet output renderer**, so that table
and query results can be downloaded as `.parquet` the same way they can be
downloaded as `.json` and `.csv` today.

Read the codebase before you design against it. `datasette/hookspecs.py`
declares the `register_output_renderer` hook, and `datasette/blob_renderer.py`
is a small in-tree renderer worth reading as an exemplar of the shape a
renderer takes.

The design document should cover:

- where the renderer is registered and how it is wired into the existing
  request path;
- the mapping from SQLite's type affinities to Parquet's typed columns,
  including the cases where it is lossy or ambiguous;
- how large result sets are handled, given that Parquet is a columnar format
  written in row groups rather than streamed row by row like CSV;
- the new dependency this introduces and what it costs;
- how the change would be tested.

Write the document to a file in the workspace root. Do not implement the
renderer — the deliverable is the design.
