import { getAllCategories, getAddedTransactionsByCategory } from "../api/endpoints";
import { useState, useEffect } from "react";
import { Box, Stack, Center, Heading,  } from "@chakra-ui/react"
import { BarList, useChart} from "@chakra-ui/charts";

export default function Dashboard() {
    const [valuesSummedByCategory, setvaluesSummedByCategory] = useState([]);
    const [categories, setCategories] = useState([]);

    useEffect(() => {
        Promise.all([
            getAllCategories(),
            getAddedTransactionsByCategory()
        ]).then(([categoriesData, transactionsData]) => {
            setCategories(categoriesData.data);
            if (transactionsData) {
                setvaluesSummedByCategory(transactionsData.data)
            }
        });
    }, []);

    const organizedCategories = []

    for (const r of valuesSummedByCategory) {
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
            name: item.name,
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
                pt={20}
            >   
                <Heading size={"2xl"}>
                    Dashboard
                </Heading>

                <Box width="100%">
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