import { Tabs } from "@chakra-ui/react";

export function DateFilter({ filterChange }) {
    return (
        <Tabs.Root defaultValue="all">
            <Tabs.List>
                <Tabs.Trigger value="all" onClick={() => filterChange(null)}>
                    Tudo
                </Tabs.Trigger>
                <Tabs.Trigger value="today" onClick={() => filterChange("day")}>
                    Hoje
                </Tabs.Trigger>
                <Tabs.Trigger value="this-month" onClick={() => filterChange("month")}>
                    Este Mês
                </Tabs.Trigger>
            </Tabs.List>
        </Tabs.Root>
    )
}