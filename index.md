# Using This Salt Bundle Repository

## 1. Adding the Repository to Salt Bundle

Add this repository as a Salt Bundle source:

```bash
salt-bundle add-repo   --name main   --url https://someblackmagic.github.io/salt-incus-formula/
```

This creates an entry in your project `.salt-dependencies.yaml` or global config `~/.config/salt-bundle/config.yaml`:

```yaml
repositories:
  - name: incus
    url: https://someblackmagic.github.io/salt-incus-formula/
```

## 2. Initializing a Salt Project

```bash
mkdir my-project
cd my-project
salt-bundle init --project
```

A `.saltbundle.yaml` file will be created in the project root.

## 3. Adding Formula Dependencies

Edit `.saltbundle.yaml` and add formulas:

```yaml
name: my-project
version: 1.0.0

dependencies:
  <formula-name>: "^1.0.0"
```

## 4. Installing Formulas

Install all dependencies:

```bash
salt-bundle install
```

This creates:

```
salt-bundle.lock
vendor/
```

Update dependencies:

```bash
salt-bundle install --update-lock
```

## 5. Verifying Installed Formulas

```bash
salt-bundle verify
```

This ensures all formulas match the lock file.
