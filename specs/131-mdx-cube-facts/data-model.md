# Data model: 131

## Error codes

| Code                  | When                                                                      |
| --------------------- | ------------------------------------------------------------------------- |
| `INVALID_PARAMS`      | `what=sa_schema` with an empty `name` or a `name` that is not a URL       |
| `SA_SCHEMA_NOT_FOUND` | `what=sa_schema` with a URL that IRIS answers 404 or with an empty result |

Both carry the same guidance: `name` is an XData namespace URL such as `http://www.intersystems.com/deepsee`; cubes are listed by `%DeepSee.Utils` `%GetCubeList` and `%GetDimensionList`, run through `iris_execute`.

## Fixture rows

See `research.md` § Fixture for the row table and the counts derived from it.
