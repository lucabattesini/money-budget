import { Skeleton, Spinner } from "@chakra-ui/react";

export function SkeletonLoading({componentHeight, componentWidth}) {
    return (
        <Skeleton 
        height={componentHeight}
        width={componentWidth}
        />
    )
}

export function SpinnerLoading() {
    return (
        <Spinner
        animationDuration="0.8s"
        />
    )
}