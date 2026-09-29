# MDX fixture cube (spec 131)

A BI cube small enough to check by hand. It needs no Samples-BI. `tests/integration/test_mdx_131_live.rs` builds it in USER, runs its queries, and drops it.

## Classes

- `IadLive131.Sale`: the `%Persistent` source table.
- `IadLive131.SalesCube`: cube `IadLive131Sales` over `Sale`.
- `IadLive131.OtherCube`: cube `IadLive131Other` over `Sale`. It exists so a query on `IadLive131Sales` can name a dimension that belongs to another cube.

## Dimensions of `IadLive131Sales`

| Dimension  | Path                                 | Key                                                                                        |
| ---------- | ------------------------------------ | ------------------------------------------------------------------------------------------ |
| `RegionD`  | `[RegionD].[H1].[Region]`            | the string, so the caption is the key                                                      |
| `ChannelD` | `[ChannelD].[H1].[Channel Name]`     | `rangeExpression` maps 1/2/3 to Retail/Online/Phone, and the mapped name becomes the key |
| `DateD`    | `[DateD].[Actual].[YearSold]`, `[MonthSold]` | the year, or the month and year                                                    |
| `DoctorD`  | `[DoctorD].[H1].[Doctor]`            | the integer id; the caption comes from the `Name` property (`DoctorName`)                  |

Measures: `%COUNT` (headed "Count") and `Amount` (SUM).

## Rows

| Region   | Channel    | Date       | Doctor     | Amount |
| -------- | ---------- | ---------- | ---------- | ------ |
| Asia     | 1 Retail   | 2023-03-10 | 11 (Smith) | 100    |
| Asia     | 2 Online   | 2023-07-04 | 12 (Jones) | 50     |
| Asia     | 2 Online   | 2024-03-15 | 11 (Smith) | empty  |
| Europe   | 1 Retail   | 2024-01-20 | 13 (Smith) | 200    |
| Europe   | 1 Retail   | 2024-03-02 | 12 (Jones) | 30     |
| Europe   | 3 Phone    | 2024-07-19 | 13 (Smith) | 70     |
| Americas | 2 Online   | 2024-11-11 | 11 (Smith) | 40     |
| Americas | 1 Retail   | 2023-11-30 | 12 (Jones) | 10     |

Europe has no 2023 row, which is what the NON EMPTY test needs. Doctors 11 and 13 share the caption Smith: 11 has three rows and 13 has two. The totals are 8 rows and an Amount of 500. By region the Amount is Americas 50, Asia 150 and Europe 300; by year it is 2023 160 and 2024 340.

## Building it by hand

Put and compile the three classes in USER in the order above. Write the rows, then:

```objectscript
Do ##class(%DeepSee.Utils).%BuildCube("IadLive131Sales",0,0)
Do ##class(%DeepSee.Utils).%BuildCube("IadLive131Other",0,0)
```

To drop it, `%KillCube` both cubes, `%KillExtent` on `IadLive131.Sale`, and then `$system.OBJ.DeletePackage("IadLive131")`.
