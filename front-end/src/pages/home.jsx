import { Button, Link, Drawer, Portal, CloseButton, Stack } from "@chakra-ui/react";

export default function Home() {
    return (
      <Drawer.Root size="xs">
        <Drawer.Trigger>
          <Button variant="outline" size="sm">
            Menu
          </Button>
        </Drawer.Trigger>
        <Portal>
          <Drawer.Backdrop/>
          <Drawer.Positioner>
            <Drawer.Content>
              <Drawer.Body>
                <Stack
                gap={5}
                pt={20}>
                  <Link href="/"
                  fontSize="lg"
                  fontWeight="bold">Dashboard</Link>

                  <Link href="/report-expense"
                  fontSize="lg"
                  fontWeight="bold">Report Expense</Link>

                  <Link href="/transactions"
                  fontSize="lg"
                  fontWeight="bold">Transactions</Link>

                  <Link href="/investments"
                  fontSize="lg"
                  fontWeight="bold">Investments</Link>
                </Stack>
              </Drawer.Body>
              <Drawer.CloseTrigger asChild>
                <CloseButton size="sm" />
              </Drawer.CloseTrigger>
            </Drawer.Content>
          </Drawer.Positioner>
        </Portal>
      </Drawer.Root>
    );
}