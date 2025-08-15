"use client"

import { BarList, useChart} from "@chakra-ui/charts";
import { useState, useEffect } from "react"
import { Stack, Center, Heading, Box } from "@chakra-ui/react"
import { getAllCategories, getAddedTransactionsByCategory } from "../api/endpoints";

export default function Dashboard() {
    const [categoriesAdded, setCategoriesAdded] = useState([]);
    const [categories, setCategories] = useState([]);
    const organizedCategories = []
    useEffect(() => {
            getAllCategories().then(data => setCategories(data.data))
        }, []);

    useEffect(() => {
        getAddedTransactionsByCategory().then(data => setCategoriesAdded(data.data))
        }, []);

    for (const r of categoriesAdded) {
        const categorieName = categories.find(element => element.id == r.category)

        if (!categorieName) continue;
        const organizedCategory = {
            name: categorieName.name,
            value: r.total / 100
        };

        organizedCategories.push(organizedCategory);

    }

    const chart = useChart({
        sort: { by: "value", direction: "desc"},
        data: organizedCategories.map((item) => ({
            name: `${item.name} `,
            value: item.value
        })),
        series: [{name: "name", color: "teal.subtle"}],
    });
    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading>
                    Dashboard
                </Heading>
                <Box w="100%">
                    <BarList.Root chart={chart}>
                        <BarList.Content>
                            <BarList.Bar/>
                            <BarList.Value/>
                        </BarList.Content>
                    </BarList.Root>
                </Box>
            </Stack>
        </Center>
    )
}