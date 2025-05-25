use anyhow::Result;
use foro_tombi::format::format;
use std::path::PathBuf;
use std::time::Instant;

fn main() -> Result<()> {
    let res = format(
        PathBuf::from("pyproject.toml"),
        r#"
[project]
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = []
name = "aaa"

    "#
        .to_string(),
        PathBuf::from("."),
    )?;

    println!("{:?}", res);
    println!("{:?}", Instant::now());

    Ok(())
}
