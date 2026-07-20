# Acme.Fixture — experiment seed project

A minimal but real ABP application module. It compiles on its own and gives an
agent a realistic place to add code during a skill-value experiment: an
`AbpModule` with `[DependsOn]`, a `FullAuditedAggregateRoot<Guid>` entity, and an
`ApplicationService`.

It is **not** a full solution template — it is deliberately small so the agent's
own additions dominate what gets measured. See `../EXPERIMENT.md`.

The `.csproj` carries no package versions. `run_experiment.py` copies the fixture
into a temp workspace and writes a `Directory.Packages.props` there, reusing the
`<AbpVersion>` from `eng/compat/Directory.Packages.props` so the experiment and the
compile-smoke suite share one version pin.
