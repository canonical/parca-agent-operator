# Contributing

![GitHub License](https://img.shields.io/github/license/canonical/parca-agent-operator)
![GitHub Commit Activity](https://img.shields.io/github/commit-activity/y/canonical/parca-agent-operator)
![GitHub Lines of Code](https://img.shields.io/tokei/lines/github/canonical/parca-agent-operator)
![GitHub Issues](https://img.shields.io/github/issues/canonical/parca-agent-operator)
![GitHub PRs](https://img.shields.io/github/issues-pr/canonical/parca-agent-operator)
![GitHub Contributors](https://img.shields.io/github/contributors/canonical/parca-agent-operator)
![GitHub Watchers](https://img.shields.io/github/watchers/canonical/parca-agent-operator?style=social)

This documents explains the processes and practices recommended for contributing enhancements to this operator.

- Generally, before developing enhancements to this charm, you should consider [opening an issue](https://github.com/canonical/parca-agent-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev) or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines:
  - code quality
  - test robustness
  - user experience for Juju administrators this charm
- When evaluating design decisions, we optimize for the following personas, in descending order of priority:
  - the Juju administrator
  - charm authors that need to integrate with this charm through relations
  - the contributors to this charm's codebase
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto the `main` branch. This also avoids merge commits and creates a linear Git commit history.

## Developing

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

### Testing

```shell
tox -e fmt           # update your code according to linting rules
tox -e lint          # code style
tox -e unit          # unit tests
tox -e integration   # integration tests
tox                  # runs 'lint' and 'unit' environments
```

### Setup

This is a machine charm, so the only requirement is the juju snap (and a lxd controller): see [this guide](https://canonical-juju.readthedocs-hosted.com/en/latest/user/howto/manage-your-deployment/manage-your-deployment-environment/#manage-your-deployment-environment) to get started.

### Build

Build the charm in this git repository using:

```shell
charmcraft pack
```

### Snap

This charm deploys and operates [this snap]( https://github.com/parca-dev/parca-agent)

### Deploy

```sh
# Create a model
juju add-model parca-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
juju deploy ./parca-agent_ubuntu@22.04-amd64.charm  parca-agent
```
