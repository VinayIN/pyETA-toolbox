import click

@click.group()
def cli():
    """Root command for your application."""
    pass

@cli.command()
@click.argument('name')
def greet(name):
    """Greets a person."""
    click.echo(f'Hello, {name}!')

@cli.command()
@click.argument('number', type=int)
def factorial(number):
    """Calculates the factorial of a number."""
    result = 1
    for i in range(1, number + 1):
        result *= i
    click.echo(f'The factorial of {number} is {result}')

if __name__ == '__main__':
    cli()