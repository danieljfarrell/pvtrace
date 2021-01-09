# LSC with Lumogen Red Dye and PMMA background absorption

!!! info
    This tutorial assumes you have followed tutorial [LSC with Lumogen Red Dye](lsc_with_luminophore.md).

This tutorial shows how to add a luminophore and absorber components to and LSC node.

## Scene

Starting with the YAML file from the tutorial on [LSC with Lumogen Red Dye](lsc_with_luminophore.md) we make the following additions to add a linear background absorption coefficient. 

This is a simple approach to include the absorption coefficient of the host material such as PMMA.

```YAML hl_lines="19 53-55"
{!lsc_pmma_background/tutorial001.yml!}
```

## Run simulation

Using the CLI we can run this simulation.

```bash
{!lsc_pmma_background/tutorial002.sh!}
```

This command will create a database file `scene.sqlite3` in the same directory as the YAML file.

## Ray statistics

In tutorial [LSC with Lumogen Red Dye](lsc_with_luminophore.md) we observed that pvtrace was killing some rays which had extremely long path lengths in the waveguide.


### Killed

The killed count is *zero* because with the addition of background absorption coefficient the threshold for killing a ray is never reached.

```bash
{!lsc_pmma_background/tutorial003.sh!}
```

  Type        | Count
------------- | -------------
Killed        | 0

### Incident and luminescent rays

 Kind         |   source: green-laser   |   source: my-lumogen-dye  
------------- | ----------------------- | -------------------------
Escaping      | 113                     | 3209
Lost          | 72                      | 435
Reflected     | 171                     |
Entering      | 3829                    |

The statistics in the table above can be generated using the CLI commands

```bash
{!lsc_pmma_background/tutorial004.sh!}
```

Let's get the luminescent rays escaping from the top and bottom surfaces,

 Surface      | Escaping
------------- | -------------
Bottom        | 798
Top           | 630

### Collection efficiency

!!! warning
    There are many different LSC metrics and different authors use different terms. Collection efficiency here is the fraction of absorbed rays that are transported to the sheet edges.

Collection efficiency will be underestimated because no solar cells are attached to the LSC sheet.

$$
\eta_{opt} = n_{\text{edge}} /  n_{\text{abs}} \approx \left( 3209 - 798 - 630 \right) / \left( 3829 -  113 \right) \approx 48\%
$$
