```c
// Grow Hairs
vector dir = { 0, 1, 0 };
// dir = @N;    // grow in normal direction
float len = 1.0;
int   steps = 10;
float jitter = 0.1;
float seed = 0.12345;

vector  pos = @P;
int             pr = addprim(geoself(), "polyline");

```

```c
// Start the curve with our point
addvertex(geoself(), pr, @ptnum);
for (int i = 0; i < steps; i++)
{
    pos += dir * len / steps;
    pos += (vector(rand( @ptnum + seed )) - 0.5) * jitter;

    // Clone our point to copy attributes
    int pt = addpoint(geoself(), @ptnum);
    // But write a new position
    setpointattrib(geoself(), "P", pt, pos);

    // Connect the new point to our curve.
    addvertex(geoself(), pr, pt);
    seed += $PI;
}

```