import { Tabs } from "@chakra-ui/react";

export function DateFilter({ filterChange }) {
    return (
        <Tabs.Root defaultValue="all">
            <Tabs.List>
                <Tabs.Trigger value="all" onClick={() => filterChange(null)}>
                    All
                </Tabs.Trigger>
                <Tabs.Trigger value="today" onClick={() => filterChange("day")}>
                    Today
                </Tabs.Trigger>
                <Tabs.Trigger value="this-month" onClick={() => filterChange("month")}>
                    This Month
                </Tabs.Trigger>
            </Tabs.List>
        </Tabs.Root>
    )
}