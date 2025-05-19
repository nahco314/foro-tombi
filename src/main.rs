use anyhow::Result;
use foro_tombi::format::format;
use std::path::PathBuf;
use std::time::Instant;

fn main() -> Result<()> {
    println!("{:?}", Instant::now());

    let res = format(
        PathBuf::from("Cargo.toml"),
        r#"
[package]
version = "0.2.0"
edition = "2021"
repository = "https://github.com/nahco314/foro-tombi"
name = "foro-tombi"

    "#
        .to_string(),
        PathBuf::from("."),
    )?;

    println!("{:?}", res);
    println!("{:?}", Instant::now());

    Ok(())
}
